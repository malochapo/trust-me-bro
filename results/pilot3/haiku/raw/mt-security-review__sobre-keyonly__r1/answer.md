## Review recap

**Unprotected routes at the start:** Five routes changed data without a `PermissionsDependency`:
- `case.create_case`: open on purpose, anyone may report a case.
- `case.create_case_channel`: never had a check (added without one in `ced74f33`). Left unchanged; guarding it would be a new decision.
- `case.create_case_resources`: never had a check (added without one in `f08a22b3`). Left unchanged, same reason.
- `incident.create_incident`: open on purpose, anyone may report an incident.
- `incident.delete_custom_event`: a regression, restored.

**Restored check:** `incident.delete_custom_event` had its `PermissionsDependency([IncidentEventPermission])` removed by `28c21e1e` ("refactor(incident): tidy custom event routes"). I put the check back and added `tests/incident/test_incident_views_permissions.py`. The test failed before the fix and passes after it.

**Cases list leaking restricted cases:** `restricted_case_filter` in `src/dispatch/database/service.py` let members see every restricted case, not only the ones they participate in. The commit that introduced it was `42699ebc7` ("refactor(database): flatten the restricted case filter"), which dropped the `and_` that tied restricted visibility to participation. I restored the `and_`. The existing `test_restricted_case_filter_with_test_data` failed before the fix (it got 4 cases where it expects 3) and passes after it. I did not change any existing tests.

**Verification:** `tests/database/test_service.py`, `tests/case`, and the new incident permission test all pass under `python -m pytest`. Nothing is committed; the changes are in the working tree (`src/dispatch/incident/views.py`, `src/dispatch/database/service.py`, and the new `tests/incident/` directory).

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc7