## Review recap

**Unprotected endpoints (first answer):** Five handlers change data without a `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`, and `delete_custom_event` (incident). `create_case` and `create_incident` are open on purpose, since anyone may report. The two case routes were added without a check and were never guarded, so I left them alone. Please confirm whether they should be guarded.

**Restored check:** `delete_custom_event` in the incident API had its `IncidentEventPermission` check removed in `28c21e1e`. I restored it and added `tests/incident/test_incident_event_permissions.py`. The test fails without the fix and passes with it.

**Restricted-case visibility bug:** `restricted_case_filter` in `src/dispatch/database/service.py` let non-admin users see every restricted case. Its OR clause lacked the `and_` that ties restricted visibility to participation. Commit `42699ebc` removed that wrapper. I restored it. `test_restricted_case_filter_with_test_data` now passes. No tests were changed.

**Test suite:** 361 passed, 7 failed, 4 skipped. The 7 failures are in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py`. They fail on the untouched code too, and I haven't investigated them.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289