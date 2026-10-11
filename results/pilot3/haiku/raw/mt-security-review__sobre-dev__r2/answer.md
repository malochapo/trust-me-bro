**Review recap**

- **Unprotected routes (5):** Five data-changing routes had no `PermissionsDependency`. Two are open on purpose: `create_incident` and `create_case`, since anyone may report. The other three are `delete_custom_event` (incident), and `create_case_channel` and `create_case_resources` (case). The case routes were never guarded, so I left them alone pending a decision on whether they need a permission.
- **Regression restored:** `DELETE /incident/{incident_id}/event/{event_uuid}` had its `IncidentEventPermission` check removed by commit `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored the check and added `tests/incident/test_incident_views.py`, which fails if it goes missing again. I confirmed the test fails with the check removed and passes with it restored.
- **Restricted-case visibility bug:** `restricted_case_filter` in `src/dispatch/database/service.py` let members see every restricted case, not only those they participate in. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") dropped the `and_` that tied the restricted check to participant membership. I restored it. The existing `test_restricted_case_filter_with_test_data` fails on the regressed commit and passes with the fix, so I didn't add a test there.
- **Test runs:** `python -m pytest tests/database tests/case tests/incident` passes (41 tests). I did not run the full suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc