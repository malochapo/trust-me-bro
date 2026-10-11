**Recap**

- **Audit:** five data-changing routes in the case and incident APIs had no `PermissionsDependency`. Two of them (`create_case` and `create_incident`) are open on purpose, because anyone may report a case or an incident.
- **Permission regression:** the incident `delete_custom_event` route lost its `IncidentEventPermission` check in commit `28c21e1e`, which was labelled a refactor. I restored the check. I also added `tests/incident/test_incident_views.py`, which fails if the check goes missing again.
- **Unconfirmed:** `create_case_channel` and `create_case_resources` have no permission check today, and I found no commit that removed one. I didn't diff their original commits (`ced74f33` and `f08a22b3`), so I can't say they never had one.
- **Visibility bug:** commit `42699ebc`, also labelled a refactor, flattened the `or_` in `restricted_case_filter`. That let non-admin users see every restricted case in the list. I restored the `and_` so a restricted case shows only to its participants. The existing tests pass (41 in `tests/database`, `tests/case` and `tests/incident`), but none of them covers this filter, and I added no test for it.
- **State:** all changes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc