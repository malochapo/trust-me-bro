Five write routes have no `PermissionsDependency` in their route definition:

**`src/dispatch/case/views.py`**
1. `POST ""` (`create_case`), line 162
2. `POST /{case_id}/resources/conversation` (`create_case_channel`), line 236
3. `POST /{case_id}/resources` (`create_case_resources`), line 260

**`src/dispatch/incident/views.py`**
4. `POST ""` (`create_incident`), line 117
5. `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`), line 503

I checked each route's decorator for a `dependencies=` argument, and neither router has router-level dependencies (`router = APIRouter()` in both files). The other write routes in both files declare a permission. No code was changed.

----- next turn -----

One of the three is a regression: `DELETE /incidents/{incident_id}/event/{event_uuid}` (`delete_custom_event`). I restored its check and added a test that fails if the check goes missing again. Nothing is committed.

**Which routes are regressions**
- **`delete_custom_event` (incident views): regression.** Commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, Jul 14 2025) deleted the line `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` and changed nothing else. The sibling event routes still have that check.
- **`create_case_channel` (`POST /cases/{case_id}/resources/conversation`) and `create_case_resources` (`POST /cases/{case_id}/resources`): not regressions.** They were added without a check, in `ced74f33` and `f08a22b3`, and no commit ever had one. They may still be a gap worth a look, but I didn't change them, since you asked only about regressions.

**Changes**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on the DELETE route, matching the other custom event routes.
- `tests/incident/test_incident_event_permissions.py` (new): finds the DELETE route on the app and asserts it carries `PermissionsDependency` with `IncidentEventPermission`. I checked it both ways: it passes with the fix, and fails with `AssertionError: DELETE custom event route is missing PermissionsDependency([IncidentEventPermission])` when the check is removed.

**Test results**
- `python -m pytest tests/case tests/incident tests/api`: 16 passed.
- The database came from the local Postgres. I passed the settings from `data/.env` as environment variables, because the app's `.env` lookup doesn't find that file from the repo root.
- The test takes the app from the `client` fixture, not `testapp`. With `testapp`, teardown failed because the test database was still in use. The same happens with any test that requests `testapp` alone, which is a pre-existing quirk in the test setup, not something this test introduced. I didn't investigate its root cause further.

----- next turn -----

The cases list leaked restricted cases because of a bug in `restricted_case_filter`. The fix is in `src/dispatch/database/service.py`, and the regression came in with commit `42699ebc`.

**Cause:** the member-role filter's `or_` had `Case.visibility == Visibility.restricted` as a standalone term. Any restricted case therefore matched, whether or not the user was a participant. The participant check was attached only to the `IndividualContact.email` term. The incident filter has the same structure correctly, with the restricted check and the participant check grouped by `and_`.

**Introducing commit:** `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, Sep 2 2025). It removed the `and_(...)` wrapper, and that changed the meaning of the filter. The original restriction was added in `b05613b5` (#6155, "sec(authz)…") and was correct at that point.

**Fix:** I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` grouping, matching the incident filter. Admin, owner, and manager roles are unchanged.

**Verification:**
- Before the fix, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` failed with `Member should see 3 cases … got 4`. That existing test was already catching the bug.
- After the fix, `python -m pytest tests/database tests/case tests/incident` gives 41 passed.
- I didn't change any existing tests and didn't add a new one, since the existing test already covers this case.

**Working tree:** this fix and the earlier `delete_custom_event` permission fix are both uncommitted. The new `tests/incident/` directory is also uncommitted.

----- next turn -----



----- next turn -----

The API handler stores the raw payload unmasked. Masking happens later, in a background job, and only overwrites the stored copy after the first commit that follows it.

**1. The POST handler (`src/dispatch/signal/views.py:70-125`)**
- `create_signal_instance` resolves the project and signal definition, then calls `signal_service.create_instance` and commits (around line 118).
- It does not call `signal_instance_create_flow`, and it doesn't use `background_tasks`, even though the parameter is declared.
- `signal_service.create_instance` (`src/dispatch/signal/service.py:650-710`) writes `raw` as a JSON round-trip of the input (line 680). No masking happens here.
- The response is `SignalInstanceRead`, which includes `raw`, so the caller gets the unmasked payload back.

**2. Masking (`src/dispatch/signal/redaction.py`)**
- Function: `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)`. It returns a copy and handles nested dicts and lists through `_redact`.
- Field names are lowercased and stripped. Matching is exact on the key name, and the whole value is replaced with `"[REDACTED]"`.
- Default keys (`src/dispatch/config.py:98-102`, overridable by the `SIGNAL_REDACTED_RAW_FIELDS` env var): `password`, `secret`, `api_key`, `session_token`, `authorization`.
- Because matching is exact, keys like `apiKey`, `x-api-key`, `token`, or `access_key` are not masked by default.

**3. Where the flow runs**
- Nothing in the request path calls the flow. The instance is picked up later by the scheduler: `main_processing_loop` (`flows.py:441`) → `process_organization_signals` (`flows.py:406`, called at line 468) → `process_signal_batch` (`flows.py:385`) → `signal_instance_create_flow` (`flows.py:46`).
- Unprocessed instances are selected by `get_unprocessed_signal_instance_ids` (`service.py:900-916`): `filter_action IS NULL` and `case_id IS NULL`, oldest first, up to 500.
- A CLI loop in `src/dispatch/cli.py` (around line 990-1010) runs the same steps inline.

**4. What the flow does, in order (`flows.py:46-230`)**
- Line 60: `signal_instance.raw = redact_raw(signal_instance.raw)` runs first, before entity extraction and before the canary and `create_case` checks.
- Entity extraction (`entity_service.find_entities`, `entity/service.py:290` uses JSONPath on `raw`) therefore only sees masked values.
- Line 78: `signal_service.filter_signal` runs snooze and dedup (`service.py:866-897`). If it sets a `filter_action`, the instance is filtered and the flow returns. Its last statement is `db_session.commit()` (line 896).
- If not filtered: canary instances are stored and returned, and instances with `create_case` off are returned as-is. Otherwise a case is created (`case_service.create`, visibility `open`) and the flow commits (line 191). Later steps read `raw`, for example the AI prompt in `ai/service.py:317`, which therefore gets masked data.

**5. Is the unmasked payload written to the database?**
Yes, briefly.
- The POST handler's commit persists the raw payload as sent.
- The flow masks in memory and its first commit persists the masked version, either the one after entity extraction (line 75, only if entity types exist) or the one in `filter_signal` (`service.py:896`, always).
- So the unmasked value stays in the `signal_instance.raw` column until the scheduler processes the row. That is up to the loop delay (60s) plus batch time, and possibly longer if processing fails. If the flow raises, `process_signal_batch` rolls back, so the row keeps the unmasked raw until a later successful run.
- Other write paths (`create_instance` callers such as `signal/flows.py:create_signal_instance` and the AWS plugin at `plugins/dispatch_aws/plugin.py`) also store unmasked raw and rely on the same later flow.
- I did not read the snooze/dedup code in `filter_snooze` and `filter_dedup`, so I haven't verified whether they touch `raw`.

Nothing was changed. The work is read-only, so there is nothing to commit. If you want, I can check whether the `signal_instance.raw` column is ever read between the POST and the scheduler run, or whether the AWS/plugin callers differ from the API path.

----- next turn -----

The entity extraction bug is fixed. The cause was commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, Sep 2 2025).

**Cause:** that commit changed the matching loop in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`, around line 289) to `jpath.find(signal_instance.raw)[:1]`. Every JSONPath therefore produced at most one entity, even when it matched several fields.

**Fix:** I removed the `[:1]` slice and the comment that went with it, so the loop again iterates over all matches. The rest of the function is unchanged. The diff is confined to that one line.

**Verification:**
- Before the fix, `tests/entity` failed on `test_find_entities_with_field_only` with `assert 1 == 2`.
- After the fix, `python -m pytest tests/entity tests/signal` gives 43 passed, 1 skipped.
- No tests were changed.

**Working tree:** this fix is uncommitted, alongside the earlier `database/service.py` and `incident/views.py` changes and the new `tests/incident/` directory. Nothing has been committed.

One consequence of the original perf change to consider: the `[:1]` slice would have been a perf win only for patterns that match many fields, and the fix gives that up. If you still want a cap, it should be a deliberate per-type limit, not a truncation of every match.

----- next turn -----

Fixed. The cause was that the `"[REDACTED]"` placeholder itself became an entity.

**Why unrelated instances grouped:** the flow masks `raw` before extracting entities (`flows.py:60`). For the "GitHub: Personal access token exposed" signal, a JSONPath aimed at `session_token` then matches the placeholder string, so every instance got the same entity value, `"[REDACTED]"`. The dedup filter on that entity type then grouped them all into one case. I didn't reproduce the full ingest flow end to end; the mechanism is confirmed by the failing tests described below.

There was a second path that could also leak. `find_entities` is called from `entity_type/service.py` and `entity_type/flows.py` on instances loaded from the database. Payloads stored before masking existed still hold the real token there.

**Fix (`src/dispatch/entity/service.py`):**
- `find_entities` now runs `redact_raw` on the payload itself before JSONPath matching. Every caller gets this, so it covers the flow and the entity-type paths.
- Matches whose value equals `MASK` are skipped.
- The masking in `redaction.py`, the default keys, and the flow are unchanged.

**Test:** new file `tests/entity/test_entity_masking.py` with three cases:
- A token payload yields no entities, and neither the mask nor the raw token appears.
- Two instances with different tokens produce no shared entity.
- Unmasked fields still produce entities, so the fix doesn't over-suppress.

Without the fix (I checked by temporarily removing the masking), the first two tests fail. I restored the file afterwards.

**Results:** `python -m pytest tests/entity tests/signal tests/database tests/case tests/incident` gives 87 passed, 1 skipped.

**Working tree:** still uncommitted, along with the earlier changes to `database/service.py`, `incident/views.py`, `entity/service.py`, and the new `tests/incident/` and `tests/entity/test_entity_masking.py` files.

----- next turn -----

**Permissions audit and regression (incident custom events)**
- Audited the write routes (POST, PUT, PATCH, DELETE) in the case and incident views at the starting commit. Five had no `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`, and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, since anyone may report a case or incident. `create_case_channel` and `create_case_resources` were never gated, so they aren't regressions. Whether they should be gated is still open.
- `delete_custom_event` was a regression: commit `28c21e1e` ("refactor(incident): tidy custom event routes") dropped its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again. Verified that it fails with the check removed and passes when restored.

**Restricted cases in the cases list**
- Members could see restricted cases they weren't participants in. In `restricted_case_filter` (`src/dispatch/database/service.py`), the restricted-visibility term stood alone in the OR, so it matched without the participant check. The incident filter already groups the two terms with `and_`.
- Introduced by `42699ebc` ("refactor(database): flatten the restricted case filter"), which removed the `and_` from the original fix in `b05613b5`. Restored the grouping. The existing `test_restricted_case_filter_with_test_data` failed (`got 4`) and now passes. No tests were changed.

**Signal payload masking and entity extraction**
- Tracing `POST /api/v1/{organization}/signals/instances`: the handler stores the raw payload without masking and returns it unmasked. The masking runs later in the scheduled processing flow, before entity extraction and before the case or filter decision. The unmasked payload does reach the database until that run commits the masked copy.
- Entity extraction (`find_entities`) returned only the first JSONPath match, because of `beb60cc4` ("perf(entity): stop at the first JSONPath match"). I removed the slice; `tests/entity` passes.
- Masked values could become entities: the `[REDACTED]` placeholder matched by a JSONPath became a shared entity, so unrelated instances were grouped by dedup. I made `find_entities` mask the payload itself and skip mask-valued matches, which also covers older unmasked payloads. Added `tests/entity/test_entity_masking.py` (3 tests, 2 of which fail without the fix). I did not reproduce the full ingest flow end to end.

**Test results:** `python -m pytest tests/entity tests/signal tests/database tests/case tests/incident` gives 87 passed, 1 skipped.

**Status:** all changes are uncommitted: `src/dispatch/database/service.py`, `src/dispatch/incident/views.py`, `src/dispatch/entity/service.py`, and the new files under `tests/incident/` and `tests/entity/test_entity_masking.py`.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95