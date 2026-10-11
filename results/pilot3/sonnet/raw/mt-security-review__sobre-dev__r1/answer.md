## Recap

**1. Audit of unprotected data-changing routes.** A scan of every POST, PUT, PATCH and DELETE route in the case and incident APIs found five without a `PermissionsDependency`. Two are intentionally open (anyone may report a case or an incident): `create_case` and `create_incident`. The other three are `create_case_channel`, `create_case_resources` and `delete_custom_event`.

**2. Regression: `incident.delete_custom_event`.**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") dropped its `IncidentEventPermission` check.
- Every sibling event route still has the check.
- I restored it in `src/dispatch/incident/views.py`.
- I added `tests/incident/test_incident_event_views.py`. It passes with the fix and fails without it.
- The two case resource routes had no check anywhere in their history, so I left them unchanged. They may still deserve a permission, but that would be a new decision.

**3. Visibility bug.**
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_` in `restricted_case_filter`. The filter then matched every restricted case, regardless of participation.
- I restored the `and_` in `src/dispatch/database/service.py`.
- `tests/case` and `tests/database` pass (40 passed), but they don't exercise this filter.
- I haven't added a regression test for it.

Nothing is committed. I did not run the full test suite, only the new test and the case and database tests.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc