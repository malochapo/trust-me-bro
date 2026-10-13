Five endpoints change data without a `PermissionsDependency` on their route:

**`src/dispatch/case/views.py`**
1. `POST ""`: `create_case`, line 162
2. `POST /{case_id}/resources/conversation`: `create_case_channel`, line 236
3. `POST /{case_id}/resources`: `create_case_resources`, line 260

**`src/dispatch/incident/views.py`**
4. `POST ""`: `create_incident`, line 117
5. `DELETE /{incident_id}/event/{event_uuid}`: `delete_custom_event`, line 503

The other 22 mutating routes in the two files declare a dependency. Neither file sets a router-level `dependencies=` on `APIRouter()`, so these five have no route-level check. I only looked at the route decorators. I did not check for permission checks inside the function bodies or in middleware, so these may still be guarded elsewhere. No code was changed.

----- next turn -----

One of the five was a regression, and I restored its check. The new test passes with the fix and fails without it.

**The regression:** `delete_custom_event` (`DELETE /{incident_id}/event/{event_uuid}`, `src/dispatch/incident/views.py`). Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line, and nothing was put back. I restored that line with the same permission class.

**Not regressions:** `create_case_channel` and `create_case_resources` were added without a permission check (`ced74f33` and `f08a22b3`), so there was no check to restore. Whether they should have one is a separate question; I left them alone. `create_case` and `create_incident` are the open-by-design ones you mentioned.

**Test:** `tests/incident/test_incident_views_permissions.py`. It looks up the `delete_custom_event` route on the incident router and asserts `IncidentEventPermission` is in its `PermissionsDependency`. Without the fix it fails, and with the fix it passes.

**Full suite:** 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. They fail the same way on the untouched tree, so they predate this change and I did not investigate them.

Nothing is committed. The changes are the one-line fix in `views.py` and the new test directory.

----- next turn -----

The cases list was showing restricted cases to members who weren't participants. The fix is in `restricted_case_filter` (`src/dispatch/database/service.py`), and it was introduced by commit `42699ebc` ("refactor(database): flatten the restricted case filter").

**Cause:** The member-role filter's `or_` had a bare `Case.visibility == Visibility.restricted` term. That term is true for every restricted case, so the participant check never applied. The commit flattened an `and_(restricted, participant-email-matches)` into three separate `or_` terms, which dropped the pairing. `restricted_incident_filter` still has the correct pairing.

**Fix:** I restored the `and_(...)` wrapper so restricted cases match only when the current user is a participant, as the incident filter does. No tests were changed.

**Verification:**
- `tests/database/test_service.py`: 25 passed. `test_restricted_case_filter_with_test_data` had been failing with "got 4" instead of 3 and now passes.
- Full suite: 361 passed, 4 skipped, 7 failed. The 7 failures are the `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py` tests that also fail on the untouched tree. I did not look into them.

Nothing is committed. Together with the earlier change, the working tree now has the `delete_custom_event` permission restore, the new permission test, and this filter fix.

----- next turn -----



----- next turn -----

**Short answer:** Masking happens in `redact_raw`, but only after the raw payload has already been committed to the database unmasked. The default keys are `password`, `secret`, `api_key`, `session_token`, and `authorization`. The unmasked payload is written to the database, and it stays there until a background worker processes the instance.

**Trace**

1. **Request handling**: `create_signal_instance` in `src/dispatch/signal/views.py` (around line 72) resolves the project and the signal definition. It then calls `signal_service.create_instance` and runs `db_session.commit()`. The route accepts `background_tasks` but never uses it, so the request does not run processing.

2. **Persistence**: `create_instance` in `src/dispatch/signal/service.py` (around line 651) builds the `SignalInstance` with `raw=json.loads(json.dumps(...))`. That is a JSON round-trip copy with no masking. The view's commit writes this to the `raw` JSONB column, so **the unmasked payload is in the database at this point.** The response also returns `raw` unmasked, through `SignalInstanceRead`.

3. **Background processing**: `main_processing_loop` and `process_organization_signals` (`signal/flows.py`, around lines 406–441) pick up unprocessed instances. `get_unprocessed_signal_instance_ids` selects rows where `filter_action` and `case_id` are null. `process_signal_batch` then calls `signal_instance_create_flow`. I did not read the bodies of the loop functions; this is based on their names and the call sites.

4. **Masking**: `signal_instance_create_flow` (`signal/flows.py:46`) runs `signal_instance.raw = redact_raw(signal_instance.raw)` at line 60, before entity extraction. The only caller of `redact_raw` is that line. The new `raw` value is stored in the row when the next commit runs.

5. **Entities and filtering**: `entity_service.find_entities` (`entity/service.py:290`) runs JSONPath matches against `signal_instance.raw`, so it sees the masked copy. Snooze and dedup run in `filter_signal`, which commits at its end. The flow then either returns early (filtered, canary, or `create_case` false) or opens a case.

**Masking details** (`src/dispatch/signal/redaction.py`)

- `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` returns a new structure in which each matching key's value becomes `"[REDACTED]"`.
- Matching is case-insensitive, exact key-name equality after lowercasing, and applies at any depth inside dicts and lists.
- Defaults come from `src/dispatch/config.py:98-102`, overridable with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable: `password,secret,api_key,session_token,authorization`.
- Because matching is exact, keys such as `apiKey`, `api-key`, `x-api-key`, `token`, or `access_token` are not masked by default.

**Gaps you should know about**

- **Unmasked at rest**: the window runs from the request commit until the worker's commit. If processing fails, `process_signal_batch` calls `rollback()`, which discards the redaction. The instance keeps `filter_action` null, so it is retried, and the unmasked payload stays in place until a run succeeds. An instance that always fails keeps its raw payload unmasked indefinitely.
- **Manual reprocessing**: `cli.py:1004` also calls the flow, so reprocessing repairs the row only if it succeeds.
- **No tests**: I found no test that references `redact` or `SIGNAL_REDACTED_RAW_FIELDS`.
- **Case creation**: I searched `signal/flows.py`, `signal/service.py`, and `case/flows.py` for `raw` reads and found no copy into case fields. I did not trace the full case-creation path, so I can't rule out other copies.

I did not change any code.

----- next turn -----

The entity extraction bug is fixed, and `tests/entity` passes (11 passed).

**Cause:** commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, Sep 2 2025) changed `_find_entities_by_jsonpath_expression` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`. That slice keeps only the first match, so a JSONPath that matches several fields produced one entity instead of one per field. The commit message assumed a JSONPath names one field, which isn't true for wildcards or recursive paths.

**Fix:** I reverted that line to `matches = jpath.find(signal_instance.raw)` and removed the comment that went with it. Nothing else changed, and no tests were modified. The performance gain the commit was after is lost, since `find` now computes all matches. If you want to keep it, the fix needs a different approach, for example stopping only once an entity has been produced for that entity type.

**Test results:**
- `tests/entity`: 11 passed. Before the fix, `test_find_entities_with_field_only` failed with `assert 1 == 2`.
- Full suite: 362 passed, 4 skipped, 6 failed. All 6 failures are in `tests/ai/test_ai_service.py`. They fail on the untouched tree too, because the code tries to download a tokenizer and there is no network access here. The earlier entity failure is gone.

Nothing is committed.

----- next turn -----

Masked values no longer become entities, so unrelated instances stop grouping on a shared `"[REDACTED]"` entity. The masking in `redact_raw` is unchanged.

**Cause:** `signal_instance_create_flow` masks `raw` before calling `find_entities`, so the JSONPath to the token matched the string `"[REDACTED]"`. That string became an entity value, identical across every instance. The dedup filter on that entity type then grouped them into one case.

The masking was not the only gap. `find_entities` is also called from `entity_type/service.py` and `entity_type/flows.py`, which run on instances that have not been through the flow yet. For those, the raw token was matched and turned into an entity.

**Fix** (`src/dispatch/entity/service.py`):
- `find_entities` now matches JSONPaths against `redact_raw(signal_instance.raw)`, so every caller extracts from the masked copy. The instance's own `raw` is not modified.
- Matches whose value equals `MASK` are skipped, so a masked value never becomes an entity.
- The masking logic itself is unchanged, and the call in the flow is still there.

**Test:** `tests/entity/test_entity_redaction.py` is new, and no existing tests were changed. It covers:
- a masked token produces no entity, even before processing;
- two instances with different tokens produce no shared entity;
- a multi-match JSONPath skips only the masked matches;
- `raw` is left unchanged after extraction.

Three of the four fail without the fix and pass with it. The fourth guards against regressions and passes either way.

**Test results:** the full suite has 366 passed, 4 skipped, and 6 failed. The 6 failures are the same `tests/ai/test_ai_service.py` tests as before. They need to download a tokenizer, and there is no network access here.

Nothing is committed.

----- next turn -----

Here is the recap for the weekly report. Nothing is committed, so the changes below are uncommitted working-tree edits.

**1. Permission review and the `delete_custom_event` regression**

I listed the POST/PUT/PATCH/DELETE routes in `src/dispatch/case/views.py` and `src/dispatch/incident/views.py` that have no `PermissionsDependency`. There are five: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`, and `delete_custom_event`. `create_case` and `create_incident` are open on purpose, since anyone may report a case or incident. `delete_custom_event` is a regression: commit `28c21e1e` ("refactor(incident): tidy custom event routes", Jul 14 2025) removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_views_permissions.py`, which fails if the check goes missing again. I did not change `create_case_channel` or `create_case_resources`. They were left unguarded by `ced74f33` and `f08a22b3`, and whether they need a check is still open.

**2. Cases list showing restricted cases to non-participants**

The member-role filter in `restricted_case_filter` (`src/dispatch/database/service.py`) had lost the pairing between "restricted" and "the user is a participant." Commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sep 2 2025) caused this. I restored that pairing. The database service tests pass, including `test_restricted_case_filter_with_test_data`, which had been failing with 4 results instead of 3.

**3. Signal instance flow (read-only trace)**

Masking happens in `redact_raw` (`src/dispatch/signal/redaction.py`), called from `signal_instance_create_flow`. It was introduced by `d2675cf4` (Jul 3 2025). The default keys are `password`, `secret`, `api_key`, `session_token`, and `authorization`. The unmasked payload is written to the database when the request commits, before processing masks it. Processing then overwrites it, but a failed run rolls back and leaves the payload unmasked.

**4. Entity extraction keeping only the first match**

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sep 2 2025) added `[:1]` to the JSONPath match in `find_entities`, which dropped every match after the first. I reverted that line, and `tests/entity` passes.

**5. Masked values becoming entities**

A "GitHub: Personal access token exposed" entity type matched the masked `session_token`. The flow had already replaced the value with `"[REDACTED]"`, so every instance produced the same entity, and the dedup filter grouped them into one case. `find_entities` now matches against a masked copy of the payload and skips any `[REDACTED]` value. This also covers the `entity_type` callers, which run before processing. The new `tests/entity/test_entity_redaction.py` fails without the fix and passes with it.

**Test status:** the full suite has 366 passed, 4 skipped, and 6 failed. The 6 failures are in `tests/ai/test_ai_service.py`. They also fail on the untouched tree, because the tokenizer download needs network access.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4