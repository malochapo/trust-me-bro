**Recap for the review report**

- **Unprotected write routes:** five data-changing routes in the case and incident APIs had no `PermissionsDependency`. Creating a case or an incident is open on purpose, so those two are intended. The other three are `create_case_channel`, `create_case_resources` and `delete_custom_event` (incident).
- **Regression fixed:** `incident.delete_custom_event` had its `IncidentEventPermission` check removed by `28c21e1e`, a commit labelled a refactor. I restored the check. I also added `tests/incident/test_incident_views.py`, which passes with the fix and fails without it.
- **Not regressions:** `create_case_channel` and `create_case_resources` never had a permission check. They are gaps, but nothing was removed. I left them alone. If you want them locked down, I can add `CaseEditPermission` to both.
- **Visibility bug fixed:** `42699ebc` ("flatten the restricted case filter") changed the case filter so any restricted case matched for every non-admin user. I restored the grouping that requires the user to be a participant. I didn't change any existing tests.
- **Test status:** `tests/database`, `tests/case` and the new test pass. `tests/ai/test_ai_service.py` has 6 failures that also occur without my changes. I haven't looked into them or run the rest of the suite.
- **State:** nothing is committed. The working tree holds both fixes and the new test.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289