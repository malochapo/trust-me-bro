## Review recap

**Permission gaps on data-changing routes.** Five POST/PUT/PATCH/DELETE handlers had no `PermissionsDependency` in their route definitions:
- `case.create_case`: open by design (anyone may report a case).
- `incident.create_incident`: open by design (anyone may report an incident).
- `case.create_case_channel` and `case.create_case_resources`: never had a check. They were added in `ced74f33` and `f08a22b3` without one, so this is an original gap, not a removal. I left them unchanged; they need a decision on which permission they should require.
- `incident.delete_custom_event`: a regression.

**Regression fixed.** `delete_custom_event` lost its `IncidentEventPermission` check in `28c21e1e`, a commit titled "refactor(incident): tidy custom event routes" that deleted only that one line. I restored the line in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views_permissions.py`. The new test fails on the HEAD version and passes with the fix. The existing `tests/case/test_case_event_views.py` tests still pass.

**Visibility bug fixed.** `restricted_case_filter` in `src/dispatch/database/service.py` lost its `and_(...)` wrapper, so any restricted case matched for any non-admin user. The fix restores the wrapper to match the incident filter. The existing tests, which were not changed, fail on the buggy version and pass with the fix (35 passed across the database and case service tests).

Nothing is committed. Both fixes are in the working tree, and I did not run the full test suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc