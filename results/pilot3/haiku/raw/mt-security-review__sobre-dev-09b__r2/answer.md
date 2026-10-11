Recap of the security review:

- **Unprotected endpoints (data-changing, no `PermissionsDependency`):** five. `POST /cases`, `POST /cases/{case_id}/resources/conversation` and `POST /cases/{case_id}/resources` in the case API; `POST /incidents` and `DELETE /incidents/{incident_id}/event/{event_uuid}` in the incident API. `POST /cases` and `POST /incidents` are open by design, so they are not findings.
- **Regression restored:** the incident `DELETE` custom-event route. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_event_route_permissions.py`, which fails if the check goes missing again. It failed before the fix and passes after.
- **Visibility bug:** `restricted_case_filter` in `src/dispatch/database/service.py` showed restricted cases to non-participants. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") split a grouped condition into two OR terms. I restored the grouping. The existing test `test_restricted_case_filter_with_test_data` fails without the fix and passes with it, and I changed no tests.
- **Not changed:** the two case resource routes (`create_case_channel`, `create_case_resources`) have never had a check, so I did not classify them as regressions. Whether they should be gated is your decision.
- **Uncommitted:** both fixes and the new test are in the working tree. Nothing is committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc