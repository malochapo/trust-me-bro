Five routes change data without a `PermissionsDependency` in their route definition:

**Incident API** (`src/dispatch/incident/views.py`)
- `POST ""`: `create_incident` (line 117)
- `DELETE /{incident_id}/event/{event_uuid}`: `delete_custom_event` (line 503)

**Case API** (`src/dispatch/case/views.py`)
- `POST ""`: `create_case` (line 162)
- `POST /{case_id}/resources/conversation`: `create_case_channel` (line 236)
- `POST /{case_id}/resources`: `create_case_resources` (line 260)

The other POST, PUT, PATCH and DELETE routes in both files declare a permission. The routers themselves (`APIRouter()` at incident line 59 and case line 61) have no router-level dependencies. I checked only the route definitions, not how `api.py` includes these routers, so any app-level dependency there is not covered. I made no code changes.

----- next turn -----

Only one of the five is a regression, and I've restored its check and added a test for it.

**Regression: `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`)**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]`. The commit message says nothing about permissions, and its diff is the one-line removal.
- I restored the line in `src/dispatch/incident/views.py`, so the route again requires `IncidentEventPermission`.

**Not treated as regressions**
- `POST /incident` (`create_incident`) and `POST /case` (`create_case`): open on purpose, as you said.
- `POST /case/{case_id}/resources/conversation` (`create_case_channel`) and `POST /case/{case_id}/resources` (`create_case_resources`): these were added without a permission check (commits `ced74f33` and `f08a22b3`) and have never had one. I can't tell from the history whether that was intended, so they're still unguarded. Let me know if they should get a permission.

**Test**
- New file `tests/incident/test_incident_views.py`. It looks up the DELETE route for `/{incident_id}/event/{event_uuid}` on the router and asserts that `IncidentEventPermission` is in its `PermissionsDependency`.
- Passes with the fix. With the check removed, it fails, which confirms it catches the regression.
- I wrote it as a structural check on the route rather than an HTTP test, so it doesn't exercise real permission enforcement. The existing case tests call view functions directly, so I followed a similar approach.

**Test run**
- `python -m pytest tests/case tests/incident` → 16 passed.
- I didn't run the full suite.

----- next turn -----

The cause is in `restricted_case_filter` (`src/dispatch/database/service.py`). The case list applies this filter, and a member gets every restricted case, including ones they aren't a participant in. The filter's last two branches were not tied together. The condition `Case.visibility == Visibility.restricted` was a standalone OR branch, so any restricted case matched regardless of participation. The incident filter has the correct version, with the restricted check and the participant email check wrapped in `and_`.

**Introducing commit:** `42699ebc` ("refactor(database): flatten the restricted case filter"). It removed the `and_(...)` around those two conditions, which is what made the restricted check unconditional.

**Fix:** I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` grouping, so restricted cases are visible only to their participants. Admin, owner and manager roles still bypass the filter as before. The test file is unchanged.

**Verification:**
- `tests/database/test_service.py::test_restricted_case_filter_with_test_data` fails on the regressed `42699ebc` version and passes with the fix, so it already covers this bug and I didn't need a new test.
- With the fix, `python -m pytest tests/database tests/case tests/incident` passes (41 tests).
- I didn't run the full suite.

**Still in the working tree from earlier:** the restored `delete_custom_event` permission in `src/dispatch/incident/views.py`, and the new test in `tests/incident/test_incident_views.py`.

----- next turn -----

**Review recap**

- **Unprotected routes (5):** Five data-changing routes had no `PermissionsDependency`. Two are open on purpose: `create_incident` and `create_case`, since anyone may report. The other three are `delete_custom_event` (incident), and `create_case_channel` and `create_case_resources` (case). The case routes were never guarded, so I left them alone pending a decision on whether they need a permission.
- **Regression restored:** `DELETE /incident/{incident_id}/event/{event_uuid}` had its `IncidentEventPermission` check removed by commit `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored the check and added `tests/incident/test_incident_views.py`, which fails if it goes missing again. I confirmed the test fails with the check removed and passes with it restored.
- **Restricted-case visibility bug:** `restricted_case_filter` in `src/dispatch/database/service.py` let members see every restricted case, not only those they participate in. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") dropped the `and_` that tied the restricted check to participant membership. I restored it. The existing `test_restricted_case_filter_with_test_data` fails on the regressed commit and passes with the fix, so I didn't add a test there.
- **Test runs:** `python -m pytest tests/database tests/case tests/incident` passes (41 tests). I did not run the full suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc