Five routes change data without a `PermissionsDependency` in their route definition. Nothing was changed.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""`: `create_case` (line 162)
2. `POST /{case_id}/resources/conversation`: `create_case_channel` (line 236)
3. `POST /{case_id}/resources`: `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""`: `create_incident` (line 117)
5. `DELETE /{incident_id}/event/{event_uuid}`: `delete_custom_event` (line 503)

The routers are plain `APIRouter()` instances with no router-level dependencies, so these five are unguarded at the route level. I did not check how `api.py` mounts the routers, so a dependency added at include time would not show up in this list.

----- next turn -----

The incident `delete_custom_event` route was a regression. I restored its check and added a test that fails if the check goes missing again. Nothing is committed.

**The regression:** commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega) removed the `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line from `DELETE /incident/{incident_id}/event/{event_uuid}`. The commit only deletes that one line, and its message doesn't mention permissions. The sibling custom-event routes (create, update, export) still have the check, so this looks accidental.

**Not regressions:**
- `create_case` and `create_incident` are the open-reporting routes you described.
- `create_case_resources` (`POST /case/{case_id}/resources`) and `create_case_channel` (`POST /case/{case_id}/resources/conversation`) were added without a guard in `f08a22b3` and `ced74f33`, so there was never a check to remove. They are a gap rather than a regression. Decide whether they should be guarded, since they change case data for any caller who can reach the route.

**Changes:**
- `src/dispatch/incident/views.py`: restored the `IncidentEventPermission` dependency on `delete_custom_event`, matching its sibling routes.
- `tests/incident/test_incident_views.py` (new): looks up the DELETE route on `dispatch.incident.views.router` and asserts that an `IncidentEventPermission` dependency is present.

**Verification:**
- With the fix, the new test passes. With the fix stashed, it fails with `assert IncidentEventPermission in []`.
- `python -m pytest tests/incident tests/case` passes (16 tests).
- I did not run the full suite.

The test originally imported `dispatch.main` or used the `testapp` fixture. Either one left a database connection open, so the test database could not be dropped at teardown. Reading the router directly avoids that, and I checked the other suites still tear down cleanly.

----- next turn -----

The cases list showed restricted cases to users who weren't participants. The fix is in `restricted_case_filter`, and the existing tests cover it. I did not change any tests and did not commit.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` has a bare `Case.visibility == Visibility.restricted` term in its OR. Any restricted case therefore passes for every non-admin role, whether or not they are a participant. The incident equivalent is correct and requires participation via `and_`.

**Introduced by:** `42699ebc7` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). The commit removed the `and_(...)` wrapper, which turned "restricted AND participant" into two separate OR terms. The commit message presents this as a flattening, but it changes the meaning.

**Fix:** restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` grouping, as it was before that commit.

**Verification:**
- `tests/database/test_service.py -k restricted_case` fails on the old code (`assert 4 == 3`) and passes with the fix, so the existing test catches this regression.
- `python -m pytest tests/database tests/case` passes (40 tests).

The `tests/incident/test_incident_views.py` change you noted is consistent with what I wrote, so I left it alone. The work from the previous findings is still uncommitted in the tree: the `delete_custom_event` permission restore, the new incident test, and this filter fix.

----- next turn -----

## Review recap

**Data-changing routes without a `PermissionsDependency`**
- `case.create_case` and `incident.create_incident` are open on purpose: anyone may report a case or an incident.
- `case.create_case_channel` and `case.create_case_resources` were never guarded. They were added without a check in `ced74f33` and `f08a22b3`, so this is a gap rather than a removed check. I did not change them. Decide whether they need a guard.
- `incident.delete_custom_event` was a regression. I restored its check.

**Restored check:** `incident.delete_custom_event` now requires `IncidentEventPermission`, as its sibling custom-event routes do. The new test `tests/incident/test_incident_views.py` fails without the check and passes with it.

**Restricted-case visibility:** `restricted_case_filter` in `src/dispatch/database/service.py` let every non-admin see all restricted cases. I restored the participant check. The existing `test_restricted_case_filter_with_test_data` fails on the old code (`assert 4 == 3`) and passes with the fix. I did not change any existing tests.

**Not run:** the full test suite. I ran `tests/incident`, `tests/case`, `tests/database` and `tests/case_cost_type`, all passing.

**Uncommitted:** the three source changes and the new test are in the working tree only.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc