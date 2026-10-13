Seven routes change data without a `PermissionsDependency`:

**Case API (`src/dispatch/case/views.py`)**
1. `POST /case` (`create_case`, line 162)
2. `POST /case/{case_id}/resources/conversation` (`create_case_channel`, line 236)
3. `POST /case/{case_id}/resources` (`create_case_resources`, line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST /incident` (`create_incident`, line 117)
5. `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`, line 503)

That is five routes. I checked each decorator in full, and none of them declares dependencies. No code was changed.

----- next turn -----

One route was a regression, and I've restored its check and added a test for it.

**Regression found:** `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`). Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from this route. The other incident event routes still have it.

**Not regressions:**
- `POST /incident` and `POST /case` are the open reporting endpoints you described.
- `POST /case/{case_id}/resources/conversation` (`create_case_channel`) and `POST /case/{case_id}/resources` (`create_case_resources`) were added without a check in `ced74f33` and `f08a22b3`. They have never been protected, so they are a gap rather than a removed check. I left them unchanged. They allow any caller to create channels and resources for an existing case, so they probably need a decision from you.

**Changes:**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on `delete_custom_event`.
- `tests/incident/test_incident_event_views.py` (new): finds the DELETE route on the incident router and asserts that `IncidentEventPermission` is in its permission classes. It passes with the fix and fails without it.

**Test results:** The full `python -m pytest` run gives 360 passed, 8 failed, 4 skipped. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. They also fail with my change stashed, so they predate this work and are unrelated. I did not commit anything.

----- next turn -----

The cases list leak came from commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sep 2 2025). Fixed.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` has an `or_` with three clauses: open, restricted, and "participant email matches". Commit `42699ebc` turned the middle `and_(restricted, participant email matches)` into two separate clauses. Any restricted case then matched on its own, so members saw restricted cases they don't participate in. The incident filter still has the correct pairing, and so did the code before the refactor.

**Fix:** I restored the `and_` pairing in `restricted_case_filter`. I did not change any tests.

**Verification:**
- `tests/database/test_service.py`: 25 passed, including `test_restricted_case_filter_with_test_data`, which failed before the fix.
- Full suite: 361 passed, 7 failed, 4 skipped. The 7 failures are in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py`. They also fail with my changes stashed, so they predate this work and are unrelated.

**Current uncommitted changes**, from this session:
- `src/dispatch/incident/views.py`: restored `IncidentEventPermission` on `DELETE /incident/{incident_id}/event/{event_uuid}`.
- `src/dispatch/database/service.py`: restored the `and_` in `restricted_case_filter`.
- `tests/incident/test_incident_event_views.py` (new): regression test for the delete permission.

I did not commit anything.

----- next turn -----

The masking happens in the background processing flow, not in the POST handler. The unmasked payload is written to the database before masking runs, and the POST response returns it unmasked. I did not change any code or run the code; this is from reading it.

**Route to the outcome**

1. **POST handler** (`src/dispatch/signal/views.py:70`, `create_signal_instance`). It resolves the project and signal definition, calls `signal_service.create_instance` (`src/dispatch/signal/service.py:650`), and commits. `create_instance` stores `raw` as given (only a JSON round-trip, `service.py:680`). No masking happens here. The response model `SignalInstanceRead` includes `raw` (`src/dispatch/signal/models.py:389-410`), so the caller gets the unmasked payload back.
2. **Queue.** The instance is stored with `filter_action` and `case_id` both NULL. A background loop (`main_processing_loop` → `process_organization_signals`, `src/dispatch/signal/flows.py:406`) picks up unprocessed rows (`get_unprocessed_signal_instance_ids`, `service.py`), in batches via `process_signal_batch` (`flows.py:385`). The CLI at `src/dispatch/cli.py:1004` also calls the same flow.
3. **Masking.** `signal_instance_create_flow` (`flows.py:46`) runs `signal_instance.raw = redact_raw(signal_instance.raw)` at `flows.py:59-60`, before any entity extraction.
4. **Entities.** Extracted from the masked `raw`, then committed if any were found.
5. **Filtering.** `filter_signal` (`service.py:866`) applies snooze and dedup, then always calls `db_session.commit()` (around `service.py:896`). If an action applies, the flow returns at this point and the instance is filtered out.
6. **Case creation.** Otherwise canary instances and instances with `create_case` off are returned as-is. Everything else creates a case from the signal definition and commits.

**The masking function**

- `redact_raw` in `src/dispatch/signal/redaction.py:10`, with the recursive helper `_redact` at line 20.
- It returns a copy in which each dict value whose key matches is replaced with `"[REDACTED]"`. Matching is case-insensitive, at any depth, inside dicts and lists. Lists are traversed, but values under non-matching keys are not inspected.
- Default keys come from `SIGNAL_REDACTED_RAW_FIELDS` (`src/dispatch/config.py:98-101`): `password`, `secret`, `api_key`, `session_token`, `authorization`. It can be overridden with an environment variable.
- Matching is exact on the key name, so `apiKey` or `api-key` would not be masked. Secrets under other key names are not masked either.
- I found no tests that reference `redact_raw` or the config setting.

**Is the unmasked payload written to the database?** Yes, in three ways:

- **Before masking.** The POST handler commits the full, unmasked `raw` before the background flow runs. That row holds the unmasked payload until the flow overwrites it.
- **If processing never reaches `filter_signal`.** An exception in the flow before that commit causes `process_signal_batch` to roll back. The row stays unmasked, and since `filter_action` is still NULL, it is retried on every loop.
- **Old versions.** Once the flow overwrites `raw`, the unmasked value may persist in Postgres WAL, dead tuples, or backups until they are cleaned up. I did not verify the retention behaviour.

The POST response also returns unmasked `raw`, and `GET /instances` returns it unmasked for any instance not yet processed.

----- next turn -----

The entity regression is fixed, and `tests/entity` passes (11 of 11).

**Cause:** commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to `jpath.find(signal_instance.raw)` in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`). For a JSONPath like `asset[*].id`, only the first match became an entity. That commit's message says "a JSONPath names one field", but `[*]` names several.

**Fix:** I removed the `[:1]` slice and its comment, so every match is extracted again. The commit's performance goal isn't kept by this change, and I did not find a cheaper way to keep it without changing behaviour.

**Correction to my earlier report:** I said `test_find_entities_with_field_only` was an unrelated, pre-existing failure. It was this regression, and it now passes.

**Full suite:** 362 passed, 6 failed, 4 skipped. The 6 failures are all in `tests/ai/test_ai_service.py`. They also failed before I touched the entity code. I checked that by stashing only the incident views change, so I have not verified them against a clean checkout. They are unrelated to the entity and database changes here, but I did not diagnose them.

**Uncommitted changes in the working tree:**
- `src/dispatch/incident/views.py`: restored the `IncidentEventPermission` check on the custom event delete route.
- `src/dispatch/database/service.py`: restored the participant check in `restricted_case_filter`.
- `src/dispatch/entity/service.py`: removed the `[:1]` slice.
- `tests/incident/test_incident_event_views.py` (new): regression test for the delete permission.

I did not commit anything.

----- next turn -----



----- next turn -----

Entities are no longer extracted from masked values, so a PAT signal's token can't become a shared entity and group unrelated instances.

**Cause:** `signal_instance_create_flow` masks the payload with `redact_raw`, which replaces a value under a key like `api_key` with the string `"[REDACTED]"`. The entity JSONPath still matched that key, so it matched the placeholder string. Every instance then got an entity with the value `[REDACTED]`, and the deduplication filter on that entity grouped them all. Masking itself was working; the extraction ran on the masked output, but nothing stopped the placeholder from becoming a value.

**Fix (`src/dispatch/entity/service.py`, `find_entities`):**
- Matching now runs on `redact_raw(signal_instance.raw)`, so entity extraction masks the payload itself rather than relying on the caller having done it. That also covers instances whose payload was stored before the flow ran.
- Any match equal to `MASK` is skipped.
- Because the guard sits in `find_entities`, every caller is covered: the signal flow, `entity_type/service.py`, `entity_type/flows.py`, and the CLI path.
- `redact_raw` and its default keys are unchanged.

**Test:** `tests/entity/test_entity_redaction.py` (new file, existing tests untouched):
- `test_masked_values_do_not_become_entities`: a JSONPath on `events[*].api_key` yields no entities.
- `test_unmasked_values_still_become_entities`: a JSONPath on `events[*].name` still yields `alice` and `bob`.

Without the fix, the first test fails, since the unmasked raw produces two token entities.

**Results:** `tests/entity`, `tests/signal` and `tests/database` pass (70 passed, 1 skipped). The full suite gives 364 passed, 6 failed, 4 skipped. The 6 failures are the same `tests/ai/test_ai_service.py` tests as before. Their error is a `tiktoken` encoding download from `openaipublic.blob.core.windows.net`, which fails because this sandbox has no network access. So they are an environment issue, not a code regression. The earlier stash check doesn't prove that; this error does.

**Not covered:** `find_entities` has a `regular_expression` field on entity types, but the extraction code only uses JSONPath, so regex-only entity types extract nothing. I did not change that. The unmasked-raw persistence issue from the earlier trace is also still unfixed, since you asked for a trace only.

----- next turn -----

## Weekly recap

**Write-endpoint permission review**
- Five write handlers had no `PermissionsDependency` before my changes. Three are in `case/views.py` and two in `incident/views.py`.
- `case.create_case` and `incident.create_incident` are open on purpose, since anyone may report a case or incident.
- `case.create_case_channel` and `case.create_case_resources` have never had a check. They look like design gaps, not regressions, so I left them unchanged for a decision.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` ("tidy custom event routes") removed its `IncidentEventPermission` check. I restored it, and `tests/incident/test_incident_event_views.py` fails if the check goes missing again.

**Restricted case visibility leak**
- Members could see restricted cases they did not participate in. The cause was `restricted_case_filter` in `src/dispatch/database/service.py`. Commit `42699ebc` ("flatten the restricted case filter") split the `and_` condition into separate clauses, which dropped the participant check. I restored the combined condition.
- `tests/database/test_service.py::test_restricted_case_filter_with_test_data` now passes, and the test is unchanged.

**Signal instance masking trace**
- Masking happens in `redact_raw` in `src/dispatch/signal/redaction.py`. It is called from `signal_instance_create_flow` in `src/dispatch/signal/flows.py`, and it was introduced in commit `d2675cf4`.
- Default masked keys: `password`, `secret`, `api_key`, `session_token`, `authorization`. Keys can be overridden with `SIGNAL_REDACTED_RAW_FIELDS`.
- The unmasked payload is written to the database. The POST handler commits the raw payload before the masking flow runs, and the response returns it unmasked. Masking only happens later in the processing flow.
- Still open, as you asked for a trace only: the unmasked payload is persisted, and the payload is returned unmasked in the POST response. Masking matches exact key names only, and there are no tests for `redact_raw`.

**Signal grouping by masked entity (PAT signal)**
- Masked values were turned into entities. `redact_raw` replaces a secret with `"[REDACTED]"`, and the entity JSONPath still matched that placeholder. Every instance then shared one `[REDACTED]` entity, and the deduplication filter grouped them into one case.
- Fix in `find_entities` (`src/dispatch/entity/service.py`): matching runs on a redacted copy of the payload, and any match equal to the mask is skipped. Masking itself is unchanged.
- New tests in `tests/entity/test_entity_redaction.py` cover masked and unmasked values.

**Entity extraction keeps only the first match**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added a `[:1]` slice to the JSONPath results. I removed the slice, so every match is extracted again.
- `tests/entity` passes (11 of 11).

**Test status:** the full suite gives 364 passed, 6 failed, 4 skipped. The 6 failures are in `tests/ai/test_ai_service.py`. They need a `tiktoken` encoding download, which fails because the sandbox has no network access. They are an environment issue, not a regression from these changes, but I have not confirmed that on a networked machine.

All changes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4