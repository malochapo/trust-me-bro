Five routes change data without a `PermissionsDependency` on their route definition:

**`src/dispatch/case/views.py`**
1. `POST ""`: `create_case` (line 162)
2. `POST /{case_id}/resources/conversation`: line 236
3. `POST /{case_id}/resources`: line 260

**`src/dispatch/incident/views.py`**
4. `POST ""`: `create_incident` (line 117)
5. `DELETE /{incident_id}/event/{event_uuid}`: `delete_custom_event` (line 503)

I checked every POST, PUT, PATCH and DELETE route in both files. The other mutating routes each declare a `PermissionsDependency` in their decorator. Neither router is created with router-level dependencies (`APIRouter()` at case/views.py:61 and incident/views.py:59), and none of these five add one through their function parameters. I made no code changes.

----- next turn -----

I restored the missing permission check on the incident custom-event delete route and added a test that catches it if it goes missing again. The full suite gives 360 passed, 8 failed, 4 skipped. The same 8 tests fail on the unmodified code, so my change did not cause them.

**Which routes are regressions**

Of the five routes from my first answer, only one is a regression:
- **`DELETE /{incident_id}/event/{event_uuid}`** (`delete_custom_event`, `src/dispatch/incident/views.py`). Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` dependency. Its sibling custom-event routes kept theirs, so this looks like an accidental side effect of the refactor.
- The case resource routes (`POST /{case_id}/resources` and `POST /{case_id}/resources/conversation`) were added without a check in `f08a22b3` and `ced74f33`. I found no evidence they were ever guarded, so I treated them as unguarded by design and left them alone.
- The two create endpoints (`POST ""` on cases and incidents) are open by design, as you said.

**Changes**

- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on the delete route, matching the original line from before `28c21e1e`.
- `tests/incident/test_incident_event_routes.py` (new): looks up the route on the incident router and asserts that it declares a `PermissionsDependency` containing `IncidentEventPermission`. It needs no database.

I confirmed the new test fails with the fix stashed and passes with it applied.

**Test failures**

The 8 pre-existing failures are in `tests/ai/test_ai_service.py` (6 tests), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I did not investigate their causes.

----- next turn -----

The cases list no longer shows restricted cases to people who aren't participants. The cause was in `restricted_case_filter` (`src/dispatch/database/service.py`). The `or_` had a bare `Case.visibility == Visibility.restricted` clause, so any non-admin user saw every restricted case in the project. The participant-email check was no longer tied to it.

**Introducing commit:** `42699ebc7` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). It removed an `and_(...)` wrapper that paired the restricted check with the participant email match. Before that, `b05613b57` (#6155) had the correct form. The filter now matches the incident version.

**Fix:** I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` clause in `restricted_case_filter`. I did not touch any tests.

**Verification:**
- `tests/database/test_service.py` passes (25 tests). `test_restricted_case_filter_with_test_data` was one of the failures from the earlier run and now passes.
- Full suite: 361 passed, 7 failed, 4 skipped. The 7 failures are in `tests/ai/test_ai_service.py` (6) and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They also fail on the unmodified code, so I left them alone.

Earlier I said 8 tests failed on the original code. That was correct, and this fix accounts for the eighth.

----- next turn -----

## Review recap

**Unprotected data-changing routes:** five handlers had no `PermissionsDependency`.
- `case.create_case` (`POST ""`) and `incident.create_incident` (`POST ""`) are open by design: anyone may report a case or incident.
- `case.create_case_channel` and `case.create_case_resources` (`POST /{case_id}/resources/conversation` and `POST /{case_id}/resources`) were added without a check in `ced74f33` and `f08a22b3`. I found no sign they were ever guarded, so I left them open. You may want to confirm that is intended.
- `incident.delete_custom_event` (`DELETE /{incident_id}/event/{event_uuid}`) was a regression.

**Restored check:** `incident.delete_custom_event` now declares `PermissionsDependency([IncidentEventPermission])`. `tests/incident/test_incident_event_routes.py` is new. It fails when the check is missing and passes with it.

**Visibility bug:** `restricted_case_filter` in `src/dispatch/database/service.py` let non-admin users see every restricted case in a project. The restricted-visibility check was no longer paired with the participant email match. I restored that pairing, matching the incident filter. `tests/database/test_service.py` passes (25 tests), including `test_restricted_case_filter_with_test_data`.

**Test status:** the full suite gives 361 passed, 7 failed, 4 skipped. The 7 failures are in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They also fail on the unmodified code, and I did not investigate them.

**Not committed:** the changes are in the working tree only.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc7