**Review recap**

- **Unprotected write routes (before changes):** five routes in the case and incident views had no `PermissionsDependency`. Three are open by design: `create_case`, `create_incident`, and `create_case_resources`/`create_case_channel`, which you confirmed are intentional. Wait, that is four: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`. The fifth is `delete_custom_event`, which is the regression below. I did not change the open-by-design routes.
- **Regression restored:** `delete_custom_event` in `src/dispatch/incident/views.py` had lost its `IncidentEventPermission` check in `28c21e1e` (2025-07-14, "refactor(incident): tidy custom event routes"). I restored it and added `tests/incident/test_incident_views.py`, which fails if the check is removed again. It fails without the fix and passes with it.
- **Visibility bug fixed:** `restricted_case_filter` in `src/dispatch/database/service.py` let non-admins see every restricted case. This came from `42699ebc` (2025-09-02, "refactor(database): flatten the restricted case filter"), which removed the participant check from the restricted branch. I restored the check. The existing test `test_restricted_case_filter_with_test_data` failed before the fix (4 cases instead of 3) and passes now, along with the other database and case service tests (35 passed).

I did not run the full test suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc