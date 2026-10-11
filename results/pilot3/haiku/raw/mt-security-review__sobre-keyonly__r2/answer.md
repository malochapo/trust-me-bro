## Review recap

**Unprotected data-changing routes (before my changes):** five handlers had no `PermissionsDependency`.
- `case.create_case` (`POST /case`) and `incident.create_incident` (`POST /incident`): you confirmed these are open on purpose, since anyone can report a case or incident.
- `case.create_case_channel` (`POST /case/{case_id}/resources/conversation`) and `case.create_case_resources` (`POST /case/{case_id}/resources`): added without a check in `ced74f33` and `f08a22b3`. I found no sign they were meant to be open, but I haven't confirmed that with you.
- `incident.delete_custom_event` (`DELETE /incident/{incident_id}/event/{event_uuid}`): this one was a regression.

**Regression fixed:** `incident.delete_custom_event` lost its `IncidentEventPermission` check in `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored the check in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_route_permissions.py`. That test fails when the check is missing and passes with it. I confirmed both directions.

**Cases list visibility bug (fixed):** `restricted_case_filter` in `src/dispatch/database/service.py` let any non-admin see every restricted case, because the participant check no longer applied to them. I restored the `and_(...)` wrapper, which requires participation for restricted cases. Related tests pass (40 passed). I didn't add a regression test for this one and can add one if you want.

**Verification:** `python -m pytest tests/incident tests/case` (16 passed), and `python -m pytest tests/database tests/case tests/api` (40 passed). I didn't run the full suite.

No commits were made. Changes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc