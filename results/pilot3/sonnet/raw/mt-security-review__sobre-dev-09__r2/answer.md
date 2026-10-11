## Recap

**Unprotected routes at the start.** Five routes changed data without a `PermissionsDependency`.
- Three are open by design or older gaps: `create_case` and `create_incident` are open on purpose, since anyone may report a case or an incident. `create_case_channel` and `create_case_resources` never had a check. They may deserve a `CaseEditPermission`, but I left them alone.
- One was a regression: `incident.delete_custom_event` lost `IncidentEventPermission` in commit `28c21e1e`. I restored the check and added `tests/incident/test_incident_views.py`. The test fails without the fix and passes with it.

**Restricted cases visible to everyone.** Commit `42699ebc` ("flatten the restricted case filter") changed `restricted_case_filter` in `src/dispatch/database/service.py`. It dropped the `and_` around the restricted condition. That made every restricted case match for non-admin users, whether or not they took part. I put the `and_` back. The `tests/database` and `tests/case` suites pass (40 tests). I didn't run the full suite, and I added no regression test for this filter.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc