## Review recap

**1. Unprotected data-changing routes.** Five POST/PUT/PATCH/DELETE handlers had no `PermissionsDependency` in their route definition. `create_incident` and `create_case` are open by design, since anyone may report. The other three are described below.

**2. Regression: incident custom event delete.** `DELETE /incident/{incident_id}/event/{event_uuid}` lost its `IncidentEventPermission` check in commit `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored the check in `src/dispatch/incident/views.py`. I added `tests/incident/test_incident_custom_event_permissions.py`, which passes with the fix and fails without it.

**3. Case resource routes.** `create_case_channel` and `create_case_resources` never had a check, since they were added without one (`ced74f33` and `f08a22b3`). I did not add one, because the request was only to restore a removed check. This is a decision for you.

**4. Restricted cases visible to members.** `restricted_case_filter` in `src/dispatch/database/service.py` let every restricted case match for non-admin users. Commit `42699ebc` removed the `and_` that tied restricted visibility to participation. I restored the grouping. `tests/database/test_service.py` now passes (25 tests), and the existing tests were not changed.

**Test suite:** 361 passed, 7 failed, 4 skipped. The 7 failures are in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py`. They fail the same way without my changes, so they predate this work, and I did not investigate them.

Nothing is committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc