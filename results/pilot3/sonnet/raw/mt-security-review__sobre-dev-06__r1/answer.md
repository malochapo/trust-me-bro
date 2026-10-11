## Recap

**Unprotected routes.** Before my changes, five routes that change data declared no `PermissionsDependency`. Three are in the case API: `create_case`, `create_case_channel` and `create_case_resources`. Two are in the incident API: `create_incident` and `delete_custom_event`. You confirmed that creating a case or an incident is open on purpose.

**Regression, restored.** Only incident `delete_custom_event` had lost a check. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` dependency. I restored it and added `tests/incident/test_incident_route_permissions.py`. The test passes with the fix and fails without it.

**Not regressions.** `create_case_channel` and `create_case_resources` were added without a check (`ced74f33` and `f08a22b3`). They remain unprotected, so they are worth a design decision.

**Restricted cases visible to non-participants.** Commit `42699ebc` ("refactor(database): flatten the restricted case filter") flattened the filter in `restricted_case_filter`. Because of that, every restricted case matched for every non-admin user. I restored the `and_(restricted, participant email == user)` grouping in `src/dispatch/database/service.py`. `tests/database` and `tests/case` pass (40 tests). I didn't add a new test for this filter.

Both fixes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc