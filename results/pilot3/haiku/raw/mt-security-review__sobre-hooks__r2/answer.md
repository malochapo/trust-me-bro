**Recap**

- **Unguarded write routes (answer 1):** Five write routes had no `PermissionsDependency` before my changes. My first reply said four, but it listed five. The list is correct; the count was wrong. Three are case routes and two are incident routes. `create_case` and `create_incident` are the intentional open-to-report routes. `create_case_channel` and `create_case_resources` were added without a check and never had one, so they may warrant a separate look. `delete_custom_event` was the regression.
- **Regression restored (answer 2):** `delete_custom_event` lost its `IncidentEventPermission` check in commit `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored the check. I added `tests/incident/test_incident_route_permissions.py`, which fails when the check is missing and passes with it. The case and incident event tests pass (5 passed).
- **Visibility bug (answer 3):** `restricted_case_filter` in `src/dispatch/database/service.py` returned every restricted case to members. Commit `42699ebc` flattened an `and_(restricted, participant)` clause into separate OR'd terms. I restored the `and_`. The existing test that had failed (`test_restricted_case_filter_with_test_data`) now passes, and `tests/database`, `tests/case` pass (50 passed). I did not run the full suite.
- **Working tree:** `src/dispatch/incident/views.py` and `src/dispatch/database/service.py` are modified, and `tests/incident/` is new. Nothing is committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289