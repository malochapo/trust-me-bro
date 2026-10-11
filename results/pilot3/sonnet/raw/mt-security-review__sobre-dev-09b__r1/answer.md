**Recap for the review report**

1. **Unprotected data-changing routes.** Five POST/PUT/PATCH/DELETE routes in the case and incident APIs had no `PermissionsDependency`. Creating a case, creating an incident, and the two case resource routes (`create_case_channel`, `create_case_resources`) have never had a check. `create_case` and `create_incident` are open on purpose. The two case resource routes have never been protected, and I left them alone, but they may deserve a separate review.

2. **Regression, fixed.** `incident.delete_custom_event` (`DELETE /{incident_id}/event/{event_uuid}`) lost its `IncidentEventPermission` check in `28c21e1e`, a commit labelled a refactor. I restored the check. I added `tests/incident/test_incident_views_permissions.py`, which fails if the check goes missing again. I confirmed it fails with the fix stashed and passes with it applied.

3. **Visibility bug, fixed.** `restricted_case_filter` in `src/dispatch/database/service.py` let non-admin users see restricted cases they didn't take part in. Commit `42699ebc` ("flatten the restricted case filter") split an `and_(restricted, participant email)` into two separate `or_` terms. As a result, any restricted case matched on visibility alone. I restored the `and_`. The existing tests pass, but none of them covers this behaviour, and I didn't add one.

Both fixes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc