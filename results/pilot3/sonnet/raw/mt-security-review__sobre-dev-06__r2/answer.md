**Recap for the review report**

- **Unprotected mutating routes at the start:** I found five by reading route decorators. Two are open on purpose, because anyone may report a case or an incident. The other three are `create_case_channel` and `create_case_resources` in the case API, and `delete_custom_event` in the incident API. Other protection, such as a router-level dependency or a check inside a function body, wasn't checked.
- **Incident regression, fixed:** commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `IncidentEventPermission` from `DELETE /{incident_id}/event/{event_uuid}`. I restored it in `src/dispatch/incident/views.py`. I added `tests/incident/test_incident_event_permissions.py`, which passes with the fix and fails without it.
- **Case gaps, not fixed:** `create_case_channel` and `create_case_resources` look like gaps from the start rather than regressions. I found no commit that removed a check from either. Any authenticated user can still trigger them for any case. That needs a separate decision.
- **Visibility bug, fixed:** commit `42699ebc` ("refactor(database): flatten the restricted case filter") changed the case filter from `open OR (restricted AND participant)` to `open OR restricted OR participant`. That let every non-admin, non-manager user see all restricted cases. I restored the original grouping in `restricted_case_filter` in `src/dispatch/database/service.py`. The existing `tests/database` and `tests/case` tests pass (40). I didn't add a regression test for this one.
- **Not done:** nothing is committed, and `ruff` wasn't available, so lint and formatting are unchecked.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289