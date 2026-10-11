Four write routes have no `PermissionsDependency` in their route definition:

**`src/dispatch/case/views.py`**
- `POST ""` → `create_case` (line 162)
- `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
- `POST /{case_id}/resources` → `create_case_resources` (line 260)

**`src/dispatch/incident/views.py`**
- `POST ""` → `create_incident` (line 117)
- `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

No code was changed. I checked the decorators directly, and the routers have no router-level `dependencies`, so these are unguarded at the route level. I did not check whether the parent app mounts these routers with extra dependencies.

----- next turn -----

Only one of the four is a regression: `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`). The other three look like deliberate choices.

**The regression**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes", Jul 2025) deleted one line, the `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on this route. The commit only touched that line, so the removal was incidental to the refactor.
- The sibling custom-event routes (POST, PATCH, and exportTimeline) still require `IncidentEventPermission`. That permission allows org admins, incident commanders, scribes, and reporters.
- I restored the check exactly as it was before the removal.

**The guard test**
- New file: `tests/incident/test_incident_route_permissions.py`. It finds the DELETE route on `dispatch.incident.views.router` and asserts that `IncidentEventPermission` is among its `PermissionsDependency` classes.
- I confirmed it fails when the check is removed and passes with the fix restored.

**Not changed, and why**
- `POST /case/{case_id}/resources` and `POST /case/{case_id}/resources/conversation` were added without a permission check (`f08a22b3`, `ced74f33`) and never had one. I found no evidence they were meant to be guarded, but they may warrant a separate look.
- `POST /case` and `POST /incident` are the open-to-report routes you mentioned.

**Tests**
- `python -m pytest tests/incident/test_incident_route_permissions.py tests/case/test_case_event_views.py` → 5 passed.
- I did not run the full suite.

----- next turn -----

The cause is in `restricted_case_filter` (`src/dispatch/database/service.py`). It was introduced by commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sep 2, 2025).

**What went wrong**
- The filter is supposed to return open cases, plus restricted cases where the user is a participant.
- The refactor split the `and_(restricted, participant email matches)` clause into separate OR'd terms. Any restricted case then matched, for any user with the member role.
- The incident version of the same filter still has the correct `and_`, so only cases were affected.

**The fix**
- I restored the `and_(...)` around the restricted branch, matching `restricted_incident_filter`. This is the only code change for this issue.
- Before the fix, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` failed (member saw 4 cases, expected 3). I did not change any tests.
- After the fix, `tests/database/test_service.py`, `tests/case/test_case_service.py`, and the rest of `tests/case` pass: 50 passed.

**Current working tree**
- `src/dispatch/database/service.py`: this fix.
- `src/dispatch/incident/views.py`: the restored permission from the previous task.
- `tests/incident/test_incident_route_permissions.py`: the guard test from the previous task.

I did not run the full test suite.

----- next turn -----

**Recap**

- **Unguarded write routes (answer 1):** Five write routes had no `PermissionsDependency` before my changes. My first reply said four, but it listed five. The list is correct; the count was wrong. Three are case routes and two are incident routes. `create_case` and `create_incident` are the intentional open-to-report routes. `create_case_channel` and `create_case_resources` were added without a check and never had one, so they may warrant a separate look. `delete_custom_event` was the regression.
- **Regression restored (answer 2):** `delete_custom_event` lost its `IncidentEventPermission` check in commit `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored the check. I added `tests/incident/test_incident_route_permissions.py`, which fails when the check is missing and passes with it. The case and incident event tests pass (5 passed).
- **Visibility bug (answer 3):** `restricted_case_filter` in `src/dispatch/database/service.py` returned every restricted case to members. Commit `42699ebc` flattened an `and_(restricted, participant)` clause into separate OR'd terms. I restored the `and_`. The existing test that had failed (`test_restricted_case_filter_with_test_data`) now passes, and `tests/database`, `tests/case` pass (50 passed). I did not run the full suite.
- **Working tree:** `src/dispatch/incident/views.py` and `src/dispatch/database/service.py` are modified, and `tests/incident/` is new. Nothing is committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289