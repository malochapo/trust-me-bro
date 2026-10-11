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