Five routes change data without a `PermissionsDependency` in their route definition:

**Incident API (`src/dispatch/incident/views.py`)**
1. `POST ""`: `create_incident`, line 117
2. `DELETE /{incident_id}/event/{event_uuid}`: `delete_custom_event`, line 503

**Case API (`src/dispatch/case/views.py`)**
3. `POST ""`: `create_case`, line 162
4. `POST /{case_id}/resources/conversation`: `create_case_channel`, line 236
5. `POST /{case_id}/resources`: `create_case_resources`, line 260

I checked the decorator blocks of every POST, PUT, PATCH and DELETE route in both files. Each of the other mutating routes declares `dependencies=[Depends(PermissionsDependency([...]))]`. Neither router is created with router-level dependencies (`APIRouter()` at `case/views.py:61` and `incident/views.py:59`). This covers only the route definitions. If something outside these files, such as middleware or a parent router, enforces permissions on these paths, that isn't reflected here.

No code was changed.

----- next turn -----

One route was a regression, and I've restored its check. The other two unprotected case routes were never protected, so they're not regressions.

**The regression:** `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`) had `IncidentEventPermission` until commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, 14 Jul 2025). That one-line deletion was labelled a refactor, and it removed the check. The route was unguarded from then on.

**Not regressions:**
- `POST /{case_id}/resources/conversation` (`create_case_channel`) and `POST /{case_id}/resources` (`create_case_resources`) have never had a permission declaration in their history. I found no commit that added or removed one. Whether they should have one is a design question, and I left them alone.
- `create_incident` and `create_case` are open by design, as you said.

**Changes:**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on `delete_custom_event`, matching the version before `28c21e1e`.
- `tests/incident/test_incident_views_permissions.py` (new): looks up the registered DELETE route for `/{incident_id}/event/{event_uuid}` and asserts that `IncidentEventPermission` is among its permission classes. I checked that it fails with the check removed and passes with it restored.

**Test results** (`python -m pytest`, PostgreSQL running):
- The new test passes.
- `tests/incident`, `tests/case` and `tests/event` together: 24 passed.

I haven't committed anything. I didn't run the full test suite.

----- next turn -----

The cases list showed restricted cases to members who aren't participants. The bug came from commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2 Sep 2025).

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` used to match a restricted case only when the requesting user was a participant. The refactor flattened the condition into `or_(open, restricted, participant-email)`, so every restricted case matched regardless of participation. The incident filter wasn't touched and is correct.

**Fix:** I restored the `and_(restricted, participant-email)` grouping in that `or_`, which is how it read before `42699ebc`. The existing tests are unchanged.

**Verification:**
- `tests/database/test_service.py` and `tests/case`: 40 passed with the fix.
- `test_restricted_case_filter_with_test_data` fails on the buggy code and passes with the fix, so the existing test does catch this regression.

I haven't committed anything. The earlier `delete_custom_event` fix is still uncommitted alongside this one.

----- next turn -----



----- next turn -----

**Short answer:** the masking happens in `signal_instance_create_flow`, not in the POST handler. The POST handler writes the unmasked payload to the database before masking runs. Masking only covers the copy the flow works on, and it only persists if the flow reaches a later commit.

**1. Request path**

- `POST /instances` is `create_signal_instance` in `src/dispatch/signal/views.py:70-107`. It resolves the project, then the signal definition by variant or external id, falling back to the default. It calls `signal_service.create_instance` and commits (around line 121). It returns the instance.
- The handler declares `background_tasks` but never uses it. The handler does not run the signal flow.
- `signal_service.create_instance` (`src/dispatch/signal/service.py:650`) stores `raw` as a JSON round trip of the input (lines 680 and 737). It does no masking.

**2. Where masking happens**

- The function is `redact_raw` in `src/dispatch/signal/redaction.py`. It returns a copy with every matching value replaced by `"[REDACTED]"`.
- Matching is an exact, case-insensitive comparison of the key name, at any depth, inside dicts and lists. It is not a substring match.
- It is called at `src/dispatch/signal/flows.py:60` in `signal_instance_create_flow`. That runs before entity extraction (`flows.py:63-75`), before `filter_signal` (`flows.py:78`), and before case creation.

**3. Default keys**

`src/dispatch/config.py:98-102`, overridable through the `SIGNAL_REDACTED_RAW_FIELDS` environment variable:

`password, secret, api_key, session_token, authorization`

Because matching is exact, camelCase or hyphenated variants such as `apiKey`, `x-api-key` or `access_token` are not masked by default.

**4. Is the unmasked payload written to the database?**

Yes, in two cases:

- **At creation.** The raw payload is committed unmasked in the POST handler, before any flow runs.
- **If the flow fails.** `process_signal_batch` (`flows.py:~396-403`) rolls back on exception. If the flow fails after redaction but before its commit, the stored unmasked version remains.

The redacted version is persisted only when the flow commits. That happens in the entity commit at `flows.py:~73` when entity types exist, or in `filter_signal`'s commit (`service.py:~897`) otherwise.

Unmasked values can also survive in database backups or WAL even after the row is overwritten.

**5. After masking: entities and filtering**

- Entity extraction runs JSONPath against the redacted `signal_instance.raw` (`entity/service.py:290`). An entity keyed on a masked field will see `[REDACTED]`.
- `filter_signal` (`service.py:866`) applies snooze, then deduplication. If either sets a `filter_action`, the instance is filtered and returned without a case.
- Otherwise, canary instances are stored and returned. Instances whose signal has `create_case` false are returned. Only the remaining instances open a case.

**Not verified**

- Nothing in the repo calls `main_processing_loop` or `process_organization_signals`, so I could not confirm what runs them in production. Until the flow runs, instances stay unmasked in the database. Unprocessed instances are those with `filter_action` and `case_id` both null (`service.py:900`).
- I did not check whether `SignalInstanceRead` includes `raw` in the response.

I haven't changed any code.

----- next turn -----

The cause is commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2 Sep 2025). It added `[:1]` to the JSONPath match in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py:289`). That slice keeps only the first match, so a JSONPath that matches several fields, such as a wildcard or recursive path, produced one entity instead of one per field.

**Fix:** I removed the slice and its comment, so the line is `matches = jpath.find(signal_instance.raw)` again. That is the same code as before `beb60cc4`.

**Verification:**
- Before the fix, `tests/entity` gave 1 failed, 10 passed. The failure was `test_find_entities_with_field_only` (`assert 1 == 2`).
- After the fix, `tests/entity` gives 11 passed.
- I did not change any tests.

The commit message's premise, that a JSONPath names one field, is not true for wildcard or recursive expressions. If the performance gain matters, it would need a different approach, such as a limit only for paths known to match one field. I haven't tried one.

Nothing is committed. The working tree also still has the earlier `delete_custom_event` permission fix, the restricted-case visibility fix, and the new permission test. I ran only `tests/entity`, not the full suite.

----- next turn -----

**Cause:** Masking runs only in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`), and the masked copy is what gets stored on the instance. Entity extraction, however, goes through `find_entities` (`src/dispatch/entity/service.py`), which is also called from the entity-type paths (`entity_type/service.py:95`, `entity_type/flows.py`). Those paths read `signal_instance.raw` directly, so a payload that still holds the raw token yields that token as an entity. A session token that isn't masked on a path that skips the flow gets grouped by the dedup filter with other instances of the same token. In the reported case, the token value is what makes unrelated instances look the same.

I couldn't confirm which path produced the analysts' groupings. The code paths above are what I checked.

**Fix (`src/dispatch/entity/service.py`):**
- `find_entities` now matches JSONPath against `redact_raw(signal_instance.raw)` instead of the raw payload. This applies to every caller.
- Matches whose value is `MASK` are skipped, so a masked value never becomes an entity.
- `redact_raw` and the masking config are unchanged.

**Test:** New file `tests/entity/test_entity_masking.py`. It covers a masked key matched directly, a wildcard `$..session_token` that hits masked keys at several depths, and an unmasked `user` field that must still be extracted. I checked that the test fails when the masking is removed from `find_entities` and passes with the fix.

**Results:** `tests/signal`, `tests/entity_type` and `tests/entity`: 50 passed, 1 skipped.

**Noticed, not changed:** `entity_type/flows.py` has `entity_types = signal_instance.signal.entity_types.append(entity_type)`. `append` returns `None`, so `entity_types` is `None` and the `if entity_types:` block never runs. Recalculation for historical signals may be doing nothing. This is separate from the masking issue, so I left it alone.

Nothing is committed. The working tree now also includes the earlier fixes and this change.

----- next turn -----

Here's the recap for the weekly report. Everything below is uncommitted in the working tree.

**1. Unprotected write routes (permissions review)**
Before my changes, five write handlers had no `PermissionsDependency`. Two are intentionally open: `create_case` and `create_incident`, since anyone may report a case or incident. `create_case_channel` and `create_case_resources` have never had a check. That is a design question I have not acted on. `delete_custom_event` in `incident/views.py` had lost its check in commit `28c21e1e` (2025-07-14), so it was a regression. I restored `IncidentEventPermission` on the route and added `tests/incident/test_incident_views_permissions.py`, which fails if the check is removed. The test passes with the fix and fails without it.

**2. Restricted cases visible to non-participants**
The cases list showed restricted cases to members who were not participants. `restricted_case_filter` in `database/service.py` had lost its `and_` grouping when commit `42699ebc` (2025-09-02) flattened the filter. I restored the grouping. `test_restricted_case_filter_with_test_data` fails on the buggy code and passes with the fix. No existing tests were changed.

**3. Entity extraction returned only the first match**
Commit `beb60cc4` (2025-09-02) added `[:1]` to the JSONPath match in `entity/service.py`, so multi-match paths produced one entity. I removed the slice. `tests/entity` went from 1 failed to 11 passed.

**4. Masked values becoming entities**
Masking runs only in `signal_instance_create_flow`. Other entity paths read the stored payload directly, so an unmasked token could become an entity, and the dedup filter then grouped unrelated instances on it. `find_entities` now matches against a redacted copy and skips `[REDACTED]` values. `redact_raw` is unchanged. The new test `tests/entity/test_entity_masking.py` fails without the guard. `tests/signal`, `tests/entity_type` and `tests/entity` pass: 50 passed, 1 skipped.

**Open items**
- I haven't verified what runs `main_processing_loop`. Nothing in the repo calls it.
- `entity_type/flows.py` has `entity_types = ....append(entity_type)`, which assigns `None`. The recalculation block for historical signals may never run. I noticed this but didn't change it.
- The full test suite has not been run.

```
UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4
```