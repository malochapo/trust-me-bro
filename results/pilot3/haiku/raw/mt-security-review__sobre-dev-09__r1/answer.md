Recap of the security review, covering the three findings:

**1. Mutating routes without a `PermissionsDependency`.** Five handlers in `case/views.py` and `incident/views.py` changed data with no permission declared. Two are open on purpose: `create_incident` and `create_case`. The other three are `case.create_case_channel` and `case.create_case_resources`, which have never had a check, and `incident.delete_custom_event`, which had one until it was removed. The first answer named four routes in its list but five in its text. The five above are the full set.

**2. Regression in `delete_custom_event`.** Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `IncidentEventPermission` from `DELETE /incident/{incident_id}/event/{event_uuid}`. I restored the check in `src/dispatch/incident/views.py`. I added `tests/incident/test_incident_event_views.py`, which asserts the dependency is on the route. It fails without the fix and passes with it.

**3. Members seeing restricted cases they're not part of.** `restricted_case_filter` in `src/dispatch/database/service.py` let every restricted case through for non-admin users. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_` that ties restricted visibility to participation. I restored it. `tests/database`, `tests/case` and `tests/case_cost` pass with 59 tests, and the existing `test_restricted_case_filter_with_test_data` fails on the unfixed code. I didn't change any tests.

Both fixes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc