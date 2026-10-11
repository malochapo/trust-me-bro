## Recap

**Audit.** I checked every POST, PUT, PATCH and DELETE route in `case/views.py` and `incident/views.py` for a `PermissionsDependency` in its decorator. Five had none:
- `create_case` and `create_incident` are open on purpose, since anyone may report a case or an incident.
- `create_case_channel` and `create_case_resources` have never had a check. They were added without one in `ced74f33` and `f08a22b3`, so they are missing a check but not regressions. Whether they should get one is still open.
- `delete_custom_event` was a regression.

**Permission regression.** Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `IncidentEventPermission` from `DELETE /{incident_id}/event/{event_uuid}`. I restored it and added `tests/incident/test_incident_view_permissions.py`. The test passes with the fix and fails without it.

**Visibility bug.** Commit `42699ebc` ("flatten the restricted case filter") turned `and_(restricted, participant email)` into two separate `or_` branches. Every restricted case therefore matched for every non-admin user. I restored the `and_()` in `restricted_case_filter` in `src/dispatch/database/service.py`. `tests/database` and `tests/case` pass (40 passed). I did not run the full suite or add a test for the visibility filter.

Both fixes are in the working tree and not committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc