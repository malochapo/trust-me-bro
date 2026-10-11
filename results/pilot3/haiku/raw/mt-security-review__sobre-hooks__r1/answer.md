**Recap**

- **Unprotected routes (before my changes):** five data-changing routes had no `PermissionsDependency`. Two are open by design (`create_case`, `create_incident`), which the team confirmed. `create_case_channel` and `create_case_resources` have no protection in the history I checked, so whether they should have one is still a design question. `delete_custom_event` was a regression.
- **Permission regression:** commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed the `IncidentEventPermission` dependency from the custom event delete route. I restored it in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_route_permissions.py`. That test fails when the check is missing and passes with it.
- **Visibility bug:** commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_` around the restricted-case clause in `restricted_case_filter`. Members saw every restricted case. I restored the condition in `src/dispatch/database/service.py`. `tests/database/test_service.py` now passes in full.
- **Test status:** the full suite has 7 failures in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py`. They also fail on the original commit, so they predate this work.
- **Not committed:** all changes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc