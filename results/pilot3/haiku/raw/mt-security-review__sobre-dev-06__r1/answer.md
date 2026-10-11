Recap of the security review:

- **Permission gaps:** Five mutating routes had no `PermissionsDependency`. Creating cases and incidents is open by design. The other three are below.
- **Restored:** The custom-event delete route on incidents had its `IncidentEventPermission` check removed in `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored that check and added `tests/incident/test_incident_views_permissions.py`, which fails if the check is removed again.
- **Not changed:** The case resource routes (`create_case_channel`, `create_case_resources`) were added without a check and never had one, so I did not treat them as regressions. They may still need a permission check, since they create channels and resources for any caller who can reach them.
- **Visibility leak:** Non-admin users could see restricted cases they did not participate in. `42699ebc` ("refactor(database): flatten the restricted case filter") split the participant check out of the restricted-case condition. I restored the grouped condition in `restricted_case_filter`. The existing test `test_restricted_case_filter_with_test_data` now passes; before, it reported 4 cases where 3 were expected. I added no new test for this.
- **Verification:** `python -m pytest tests/database/test_service.py tests/case/test_case_service.py tests/case tests/incident` gives 51 passed. I did not run the full suite.
- **Working tree:** Changes are uncommitted in `src/dispatch/incident/views.py`, `src/dispatch/database/service.py`, and the new `tests/incident/` directory.

UNPROTECTED_AT_START: case.create_case_channel, case.create_case_resources, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc