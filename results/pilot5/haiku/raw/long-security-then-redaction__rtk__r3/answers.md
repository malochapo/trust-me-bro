Five write routes have no `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST /case` (`create_case`, line 162)
2. `POST /case/{case_id}/resources/conversation` (`create_case_channel`, line 236)
3. `POST /case/{case_id}/resources` (`create_case_resources`, line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST /incident` (`create_incident`, line 117)
5. `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`, line 503)

The routers are plain `APIRouter()` instances with no router-level dependencies, so nothing else covers these routes. I checked route definitions only, not whether `api_router` in `src/dispatch/main.py` adds dependencies when it is included.

No code was changed.

----- next turn -----

Only one of the five was a regression. I restored its check and added a test that fails if the check goes missing again.

**Regression: `DELETE /incidents/{incident_id}/event/{event_uuid}`**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]`. The commit's only change is that one deleted line, so it looks like an accidental drop during a cleanup.
- I restored that line in `src/dispatch/incident/views.py`, using the same check the route had before.

**Design choices, left as they were**
- `POST /incidents` and `POST /cases`: open on purpose, as you said.
- `POST /cases/{case_id}/resources` and `POST /cases/{case_id}/resources/conversation`: these have never had a check. They were added without one in `f08a22b3` (2023) and no later commit removed one. I found no evidence they were meant to be guarded, but I did not confirm the intent with anyone. If they should be restricted, that's a new decision, not a restore.

**Test**
- `tests/incident/test_incident_view_permissions.py` reads the route's dependencies from `dispatch.incident.views.router` and asserts that `IncidentEventPermission` is among the `PermissionsDependency` guards on the DELETE route.
- Before the fix, it failed with `assert [IncidentEventPermission] in []`. After the fix, it passes.
- I first wrote it against `testapp` (the full app). That left a database connection open and blocked the test database drop at teardown. Reading the router directly avoids that.

**Test run**
- The full suite gives 360 passed, 4 skipped, 8 failed. The same 8 tests fail on the original tree with my changes stashed. They are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. They predate this change and I didn't investigate them.

**Environment notes**
- `python -m pytest` in the provided venv didn't work. Its pytest was shadowed by a path injected from `_bench_deps.pth`, and the venv had no pip.
- I created a clean venv at `/tmp/sobre-bench-work/run-7df9a02b571a/cleanenv` and installed the project into it with `.[dev]`. Tests were run with `cleanenv/bin/python -m pytest`.
- PyPI needed `PIP_CERT=/etc/ssl/certs/ca-certificates.crt` because of a certificate error. I did not disable certificate checks.

----- next turn -----

The cause was in `restricted_case_filter` in `src/dispatch/database/service.py`. The commit that introduced it is `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02).

**Cause**
- For non-admin roles, the filter should return open cases, plus restricted cases where the user is a participant.
- The refactor removed the `and_(...)` wrapper around the restricted check. The filter then became `open OR restricted OR participant-email-matches`. Every restricted case passed, whether or not the user took part in it.
- The incident filter (`restricted_incident_filter`) still has the correct `and_`, so only cases were affected.

**Fix**
- I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` wrapper, the same form the filter had before the refactor. This is the only change to that file.

**Testing**
- `tests/database/test_service.py::test_restricted_case_filter_with_test_data` was failing before and now passes. The file's 25 tests all pass.
- I did not modify any tests.
- Full suite: 361 passed, 4 skipped, 7 failed. The 7 failures are in `tests/ai/test_ai_service.py` (6) and `tests/entity/test_entity_service.py` (1). They also fail on the clean tree, so they predate these changes and I did not investigate them.

**Still in the working tree from the previous task**
- The incident-event DELETE check restored in `src/dispatch/incident/views.py` and the new `tests/incident/` test, both from the previous request.

I used the clean venv at `/tmp/sobre-bench-work/run-7df9a02b571a/cleanenv` for these runs, as before. I did not commit anything.

----- next turn -----



----- next turn -----

The masking happens in the signal processing flow, not in the POST handler, so the raw payload is stored unmasked on the POST before masking runs.

**1. POST handler (`src/dispatch/signal/views.py:70`, `create_signal_instance`)**
- It resolves the project and the signal definition (by external ID or variant, else the project default; 404 if none exists).
- It calls `signal_service.create_instance` (`src/dispatch/signal/service.py:640`), which stores `raw` as received (`service.py:680`, a JSON round-trip with no masking).
- The handler then calls `db_session.commit()`. **The unmasked payload is written to the database here.**
- Nothing in this path calls `signal_instance_create_flow`. The handler also takes `background_tasks` but never uses it.
- I did not check whether the response schema (`SignalInstanceRead`) includes `raw`. If it does, the unmasked payload is also returned in the POST response.

**2. Processing (runs later, asynchronously)**
- `signals process` (`src/dispatch/cli.py:938`) or `main_processing_loop` (`src/dispatch/signal/flows.py`, around line 440) runs every 60 seconds. It selects instances with `filter_action IS NULL` and `case_id IS NULL`, in batches of 50 (`process_signal_batch`, `flows.py:385`).
- Each instance goes through `signal_instance_create_flow` (`flows.py:46`).

**3. Masking (`flows.py:59-60`)**
- `signal_instance.raw = redact_raw(signal_instance.raw)` runs before any other step, so entity extraction, filtering, and case creation all see the masked version.
- `redact_raw` is in `src/dispatch/signal/redaction.py:10`. It builds a lowercase set of the configured field names and calls `_redact`, which recurses through dicts and lists. Any dict key whose lowercased name is in the set has its whole value replaced with `"[REDACTED]"`. Other values are returned unchanged.
- Matching is exact on the key name, not substring, and applies at any depth.
- The assignment changes the ORM attribute, so the next commit persists the masked payload over the original row.

**4. Remaining path after masking**
- Entity extraction runs on the masked raw (`entity/service.py:290`, JSONPath). Commits at `flows.py:75` only if entity types exist.
- `filter_signal` (`service.py:866`) runs snooze, then dedup, then commits. A filtered instance returns here (`flows.py:78-100`).
- Canary instances (`flows.py:103`) and instances whose signal has `create_case` false (`flows.py:106`) return after masking.
- Otherwise a case is created (`flows.py:173-191`) with `visibility=open`. The case is built from the signal definition's name and description, not from `raw`.

**Default masked keys**
`SIGNAL_REDACTED_RAW_FIELDS` (`src/dispatch/config.py:98-102`) defaults to `password, secret, api_key, session_token, authorization`. It is comma-separated and can be overridden with the environment variable of the same name. Keys such as `apiKey`, `api-key`, `token`, or `x-api-key` are not masked, because the match is exact.

**Is the unmasked payload written to the database?**
Yes. The POST handler commits the raw payload before any masking. Masking is only applied to the in-memory object in the processing flow, and the later commits overwrite the column with the masked version. The unmasked value stays in the row until the processing loop runs for that instance. If the loop never runs, or the batch fails and rolls back (`process_signal_batch` rollback path), the unmasked value stays. I did not find any other table or column that stores the raw payload.

Masking was introduced in `d2675cf4` ("feat(signal): mask sensitive raw fields before processing", 2025-07-03). That commit added the redaction only to the processing flow, which is why the POST write is still unmasked.

I made no code changes and ran no tests.

----- next turn -----

The entity regression is fixed. The culprit is `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, Sep 2 2025). It changed `find_entities` in `src/dispatch/entity/service.py` (around line 289) to `jpath.find(signal_instance.raw)[:1]`, so only the first match per entity type was kept.

**Fix:** I reverted that line to `matches = jpath.find(signal_instance.raw)`, which yields every match. I removed the comment the commit added with it. No tests were changed.

**Results**
- `tests/entity` and `tests/signal`: 43 passed, 1 skipped. `test_find_entities_with_field_only` now passes.
- Full suite: 362 passed, 4 skipped, 6 failed. The 6 failures are the `tests/ai/test_ai_service.py` cases that failed before these changes. The entity failure from the previous run is gone.

**Environment:** I ran tests with the clean venv at `/tmp/sobre-bench-work/run-7df9a02b571a/cleanenv`, not `python -m pytest` in the project venv. The project venv's pytest is shadowed by a scratch path and fails at import with `No module named 'slack_sdk'`. PostgreSQL was reachable from both.

I did not commit anything.

----- next turn -----

Unrelated instances were grouped because the masked value itself became an entity. The flow masks `signal_instance.raw` at `src/dispatch/signal/flows.py:60`, and then `find_entities` extracts entities from that masked payload. The session token's JSONPath matched the string `"[REDACTED]"`, so every instance produced the same entity value. The deduplication filter on that entity type then grouped all of them. I traced this from the code, not from production data, so the mechanism is inferred rather than checked against the database.

The fix is in `src/dispatch/entity/service.py`, in `_find_entities_by_jsonpath_expression`:
- It now extracts from `redact_raw(signal_instance.raw)` instead of the raw payload. Every caller of `find_entities` gets this, not only the processing flow.
- It skips any match whose value equals `MASK`.

This also closes a second gap. `entity_type/service.py` and `entity_type/flows.py` call `find_entities` on payloads that have not been through the processing flow, so the unmasked token could become an entity value. Masking is unchanged; `redact_raw`, `MASK`, and the flow's redaction line are as they were.

**Test:** `tests/entity/test_entity_masking.py` is new. It sets an unmasked `session_token` on a signal instance and checks that no entity is produced from it. It also checks that the stored payload is not mutated, and that an unmasked field (`user.login`) still produces its entity. The test fails against the old `entity/service.py` and passes with the fix.

**Results**
- `tests/entity` and `tests/signal`: 44 passed, 1 skipped.
- Full suite: 363 passed, 4 skipped, 6 failed. The 6 failures are the same `tests/ai/test_ai_service.py` cases that failed before these changes.

**Behaviour change:** a real value that is literally `[REDACTED]` will no longer become an entity. I judged that acceptable because the mask string is indistinguishable from a masked value.

I ran tests with the clean venv at `/tmp/sobre-bench-work/run-7df9a02b571a/cleanenv`, not `python -m pytest` in the project venv (same reason as before: the venv's pytest is shadowed and fails on `slack_sdk`). I did not commit anything.

----- next turn -----

Here is the recap for the weekly report. Nothing is committed; the changes are in the working tree.

**1. Permission checks on write routes (case and incident APIs)**
- Five write handlers had no `PermissionsDependency`: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident`, and `incident.delete_custom_event`.
- You confirmed that anyone may report a case or an incident, so the two creation handlers are by design. I did not separately confirm that `create_case_channel` and `create_case_resources` are meant to be open.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored it with one line in `src/dispatch/incident/views.py`.
- A new test, `tests/incident/test_incident_view_permissions.py`, fails if that guard goes missing again. It was checked against the unfixed code.

**2. Restricted cases visible to non-participants**
- Cause: `restricted_case_filter` in `src/dispatch/database/service.py` lost the `and_` wrapper around the restricted-and-participant condition. Every restricted case passed the filter.
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sep 2 2025) introduced it. I restored the wrapper, matching `restricted_incident_filter`.
- `tests/database/test_service.py::test_restricted_case_filter_with_test_data` was failing and now passes. No tests were changed.

**3. Entity extraction keeping only the first match**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath results in `find_entities`. I reverted that line. The entity tests that had been failing now pass.

**4. Masked values becoming entities**
- Cause: the processing flow masks the payload before extracting entities, so a JSONPath pointing at a masked field matched the literal `"[REDACTED]"`. Every instance then got the same entity, and the deduplication filter grouped them. This is inferred from the code; I did not check the database.
- Two other callers, `entity_type/service.py` and `entity_type/flows.py`, extracted from unmasked payloads. This was a second gap.
- Fix: `find_entities` now extracts from `redact_raw(signal_instance.raw)` and skips any match equal to the mask. The masking itself is unchanged.
- New test: `tests/entity/test_entity_masking.py`. It fails against the old code and passes with the fix.

**Test status**
- Full suite: 363 passed, 4 skipped, 6 failed. All 6 failures are in `tests/ai/test_ai_service.py`, and they also failed before these changes. They are not investigated.
- I used the clean venv at `/tmp/sobre-bench-work/run-7df9a02b571a/cleanenv` instead of `python -m pytest` in the project venv, because the project venv's pytest is shadowed and fails on `slack_sdk`.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95