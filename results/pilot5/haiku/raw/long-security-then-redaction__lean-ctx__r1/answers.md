Five data-changing routes in these two files have no `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""`: `create_case` (line ~193)
2. `POST /{case_id}/resources/conversation`: `create_case_channel` (line ~261)
3. `POST /{case_id}/resources`: `create_case_resources` (line ~283)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""`: `create_incident` (line ~159)
5. `DELETE /{incident_id}/event/{event_uuid}`: `delete_custom_event` (line ~375)

I checked only route-level `dependencies=` declarations, as the question asked. Router-level dependencies set where these routers are mounted were not checked. I made no code changes.

----- next turn -----

The one regression is the incident `delete_custom_event` route. I restored its permission check and added a test that fails if it goes missing again. Nothing is committed.

**Regression found**
- `DELETE /{incident_id}/event/{event_uuid}` in `src/dispatch/incident/views.py` lost its `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` in commit `28c21e1e` ("refactor(incident): tidy custom event routes"). That commit's only change was deleting that line. The sibling event routes still have the check.
- The two case routes were never protected. `create_case_resources` (`POST /{case_id}/resources`) was added without a check in `f08a22b3`, and `create_case_channel` (`POST /{case_id}/resources/conversation`) in `ced74f33`. I treated them as design gaps, not regressions, and left them alone.
- Of the five unprotected routes, `create_case` and `create_incident` are the intentional open reporting endpoints. I didn't touch them.

**Changes**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on `delete_custom_event`.
- `tests/incident/test_incident_views.py` (new): looks up the DELETE route on the incident router and asserts `IncidentEventPermission` is among its `PermissionsDependency` classes. It passes with the fix. Against the HEAD version of `views.py` it fails, as intended.

**Test results**
- `python -m pytest` on the full suite: 360 passed, 4 skipped, 8 failed.
- The same 8 failures happen on clean HEAD, so they predate this change. They are in `tests/ai/test_ai_service.py` (6 tests), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I didn't investigate them.

The new test only covers the restored route. A broader check that every mutating route declares a permission would also flag the intentional open endpoints, so it would need an allowlist.

----- next turn -----

The restricted-case leak is fixed. Members now see only open cases plus restricted cases they participate in. The commit that introduced it is `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02).

**Cause**
- `restricted_case_filter` in `src/dispatch/database/service.py` checks visibility and participation as separate OR branches. The "flatten" refactor removed the `and_(...)` wrapper, so `Case.visibility == restricted` alone was enough to match.
- The incident version of the same filter still has the correct `and_`. It's the model for the fix.

**Fix**
- `src/dispatch/database/service.py`: restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` grouping inside the `or_`. This is the only change.

**Verification**
- `tests/database/test_service.py`: all 25 pass, including `test_restricted_case_filter_with_test_data`, which failed before. I didn't change any tests.
- Full suite: 361 passed, 4 skipped, 7 failed. All 7 fail on clean HEAD too: six in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I haven't looked into them.

I checked the filter at the function level, not through the HTTP cases list endpoint.

Nothing is committed. Uncommitted changes from earlier in this session are still in the tree: the restored permission check in `src/dispatch/incident/views.py` and the new `tests/incident/test_incident_views.py`.

----- next turn -----



----- next turn -----

The payload is masked later, in the background processing step, not in the POST handler. The unmasked payload is written to the database at POST time, before any masking runs.

**1. POST `/api/v1/{org}/signals/instances`** (`src/dispatch/signal/views.py:70-129`, `create_signal_instance`)
- Resolves the project, then the signal definition by `externalId`/`variant` from `raw`, falling back to the project default (404 if none).
- Calls `signal_service.create_instance(...)` and then `db_session.commit()` (lines 117-120). The request raw is stored as sent.
- It does not call `signal_instance_create_flow`, does not mask, and does not create a case. A duplicate id returns 409.

**2. `signal_service.create_instance`** (`src/dispatch/signal/service.py:650-723`)
- Builds the `SignalInstance` with `raw=json.loads(json.dumps(raw))`. This is only a JSON round-trip; no masking.

**3. Background processing**
- `process_organization_signals` (`signal/flows.py:406`) selects unprocessed instances (`filter_action IS NULL`, `case_id IS NULL`, `service.py:900-916`) and passes them to `process_signal_batch` (`flows.py:385`), called from `cli.py:938` (`process_signals`).
- `process_signal_batch` calls `signal_instance_create_flow` (`flows.py:394`) and commits per instance. On exception it rolls back.

**4. `signal_instance_create_flow`** (`src/dispatch/signal/flows.py:46-228`)
- Line 60: `signal_instance.raw = redact_raw(signal_instance.raw)`. The comment says this happens before entity extraction, so entities are found from the masked payload.
- Then entity extraction (line 69) and `db_session.commit()` (line 75) if entity types exist.
- `filter_signal` (line 78, `service.py:866-897`) applies snooze, then dedup. Filtered instances return at line 100, and `filter_signal` commits at line 896.
- Canary and `create_case=False` instances return at lines 103-107 without a case.
- Otherwise a case is created (lines 173-191, `visibility=Visibility.open`), then the case flow, engagements, and workflows run.

**Masking: where and what**
- Function: `redact_raw` in `src/dispatch/signal/redaction.py:10`, with recursive helper `_redact` at line 20. It returns a copy and replaces the value of any key whose lowercased name is in the set with `"[REDACTED]"`. It recurses into dicts and lists at any depth. Other values pass through unchanged.
- Default keys (`src/dispatch/config.py:98-102`, env `SIGNAL_REDACTED_RAW_FIELDS`): `password,secret,api_key,session_token,authorization`.
- Matching is exact after lowercasing. `apiKey`, `api-key` and `db_password` would not match `api_key`/`password` by this rule (I read the code; I did not run these cases).

**Is the unmasked payload persisted?** Yes.
- `views.py:120` commits the raw payload exactly as received, before any masking.
- The masked value is only written later, when `signal_instance_create_flow` commits at line 75, line 191, or `filter_signal`'s line 896, whichever comes first for that instance.
- So there is a window, from POST until the batch job runs, where the raw payload with secrets sits in the `signal_instance.raw` JSONB column. Those values also remain in any earlier committed row if processing never gets past `filter_signal` without committing.
- Nothing in the repo rewrites the stored `raw` at POST time. I did not check database backups, logs, or the scheduler path (`flows.py:231` `create_signal_instance`) in detail.

**Caveats**
- The docstring of `signal_instance_create_flow` says "Create flow used by the API", but the API route never calls it. Only `process_signal_batch` does.
- I did not run any code or tests for this trace.

----- next turn -----

The cause was commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02). It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`, so each JSONPath entity type produced at most one entity. I removed the `[:1]` and restored `matches = jpath.find(signal_instance.raw)`. That is the only code change.

Results:
- `tests/entity` and `tests/database/test_service.py`: 36 passed. `test_find_entities_with_field_only` (expects 2 entities, got 1) now passes.
- Full suite: 362 passed, 4 skipped, 6 failed. All six failures are in `tests/ai/test_ai_service.py` (`TestGenerateReadInSummary` and `TestGenerateTacticalReport`). I did not look into them.

I need to correct my earlier report. I said the `test_find_entities_with_field_only` failure was pre-existing and verified it on clean HEAD. That was wrong: HEAD includes `beb60cc4`, so the stash check could not show that failure predated the commit. I should have traced it then.

The changes are uncommitted. The working tree also still has the earlier `src/dispatch/database/service.py` fix, the restored permission check in `src/dispatch/incident/views.py`, and the untracked `tests/incident/`.

----- next turn -----

Unrelated "GitHub: Personal access token exposed" instances were grouped because the masked value `[REDACTED]` was extracted as an entity. Every instance got the same entity value, and the deduplication filter on that entity type then matched them together. I added a guard in `find_entities` and two regression tests. The masking itself is unchanged.

**Cause**
- `signal_instance_create_flow` masks `raw` (`src/dispatch/signal/flows.py:60`) and then calls `find_entities` (line 69). With the `session_token` key in the default redaction list, the JSONPath `session_token` matched `"[REDACTED]"`, which is a string, so it became an entity with that value.
- `find_entities` also reads the stored `raw`. Until a signal is processed, the POST handler has committed the unmasked payload, so recalculation (`entity_type/service.py:95`, `entity_type/flows.py:29`) could extract the real token. Redaction happened in one caller only, not in `find_entities`.

**Fix** (`src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression`)
- Run the JSONPath matches against `redact_raw(signal_instance.raw)`, so every caller sees the masked payload.
- Skip any string equal to `MASK`, so the placeholder never becomes an entity.
- The masking in `redaction.py` and the flow are unchanged.

**Tests** (new file `tests/entity/test_entity_redaction.py`; no existing tests changed)
- `test_find_entities_never_returns_masked_values`: one instance stored unmasked and one already masked; neither yields an entity.
- `test_find_entities_ignores_literal_mask_value`: a payload whose value is literally `[REDACTED]` yields no entity.
- Before the fix (`src/dispatch/entity/service.py` stashed): both fail. After: both pass.

**Results**
- `tests/entity`, `tests/database/test_service.py` and the new tests: 40 passed.
- Full suite: 364 passed, 4 skipped, 6 failed. The 6 failures are the same `tests/ai/test_ai_service.py` ones as before, which I haven't investigated.

**Caveats**
- `ruff` isn't installed in this environment, so I didn't run formatting checks. The new test file has a long line (the `SignalInstanceFactory(raw=...)` call in the second test) that may need reformatting.
- Existing deduplication entities already in the database are not cleaned up by this change.
- Changes are uncommitted, alongside the earlier ones in `src/dispatch/database/service.py`, `src/dispatch/incident/views.py`, and `tests/incident/`.

----- next turn -----

**Investigation 1: missing permission checks and the removed check**

I listed every POST/PUT/PATCH/DELETE route in the case and incident views that had no route-level `PermissionsDependency`. Five had none before my changes. Two are intentionally open because anyone may report a case or incident: `case.create_case` and `incident.create_incident`. Three are design gaps that I did not change: `case.create_case_channel`, `case.create_case_resources`, and `incident.delete_custom_event`.

`incident.delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored it in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views.py`, which fails if the check goes missing again. That test fails against the HEAD version of the file and passes with the fix.

**Investigation 2: cases list showing restricted cases to members**

The member branch of `restricted_case_filter` in `src/dispatch/database/service.py` lost its `and_` grouping in commit `42699ebc` ("refactor(database): flatten the restricted case filter"). Without it, any restricted case matched the filter, so members saw cases they were not part of. I restored the grouping, which matches the incident filter. `tests/database/test_service.py` passes 25/25, including the test that had been failing. I checked this at the filter-function level, not through the HTTP endpoint.

**Entity extraction: only the first JSONPath match kept**

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath match in `find_entities`. I removed it. The `tests/entity` failure is fixed. I also need to correct my earlier report: I had called `test_find_entities_with_field_only` a pre-existing failure after checking on HEAD, but HEAD already contained this commit, so that check could not show it predated the change.

**Signal-instance trace**

- The POST handler (`src/dispatch/signal/views.py:70-129`) stores the raw payload, unmasked, and commits it before any processing.
- Masking happens later in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`) via `redact_raw` in `src/dispatch/signal/redaction.py`. Default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`.
- The masking was introduced in `d2675cf4` ("feat(signal): mask sensitive raw fields before processing").
- The unmasked payload is persisted at POST time, so the answer to whether it is ever written to the database is yes.

**Masked values becoming entities**

`[REDACTED]` was extracted as an entity value. Every instance of the signal got the same entity, and the deduplication filter then grouped them. The fix is in `src/dispatch/entity/service.py`: extraction now runs on the redacted payload and skips the mask value. The masking itself is unchanged. The new tests in `tests/entity/test_entity_redaction.py` fail without the fix and pass with it.

**Test status**

- The full suite is 364 passed, 4 skipped, 6 failed. The 6 failures are in `tests/ai/test_ai_service.py`, and I have not investigated them.
- Everything is uncommitted: `src/dispatch/database/service.py`, `src/dispatch/entity/service.py`, `src/dispatch/incident/views.py`, `tests/incident/`, and `tests/entity/test_entity_redaction.py`.
- `ruff` is not installed here, so formatting is unchecked.

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