**Recap**

- **Unprotected routes:** Five routes changed data without a `PermissionsDependency`. Two of them, `create_case` and `create_incident`, are open on purpose, because anyone may report a case or an incident. `create_case_channel` and `create_case_resources` never had a check. That is probably a gap, but it isn't a regression, and I left both alone. They are still open, and you'd need to choose a permission for them. `CaseEditPermission` would match the other case mutation routes.
- **Regression restored:** The incident `delete_custom_event` route lost its `IncidentEventPermission` check in `28c21e1e`. I restored it in `src/dispatch/incident/views.py`. I added `tests/incident/test_incident_event_permissions.py`, which fails if any of the four incident timeline-event routes loses that check. It passes with the fix and fails without it.
- **Visibility bug:** `42699ebc` removed the `and_(...)` around the restricted clause in `restricted_case_filter` (`src/dispatch/database/service.py`). The filter then matched every restricted case for non-admin users. I restored the `and_`. `tests/database/test_service.py` passes (25 tests), and I didn't change any existing test.
- **Not done:** Nothing is committed. I ran only the new test and `tests/database/test_service.py`, not the full suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc