## Review recap

**Unprotected data-changing routes:** five handlers had no `PermissionsDependency`.
- `case.create_case` (`POST ""`) and `incident.create_incident` (`POST ""`) are open by design: anyone may report a case or incident.
- `case.create_case_channel` and `case.create_case_resources` (`POST /{case_id}/resources/conversation` and `POST /{case_id}/resources`) were added without a check in `ced74f33` and `f08a22b3`. I found no sign they were ever guarded, so I left them open. You may want to confirm that is intended.
- `incident.delete_custom_event` (`DELETE /{incident_id}/event/{event_uuid}`) was a regression.

**Restored check:** `incident.delete_custom_event` now declares `PermissionsDependency([IncidentEventPermission])`. `tests/incident/test_incident_event_routes.py` is new. It fails when the check is missing and passes with it.

**Visibility bug:** `restricted_case_filter` in `src/dispatch/database/service.py` let non-admin users see every restricted case in a project. The restricted-visibility check was no longer paired with the participant email match. I restored that pairing, matching the incident filter. `tests/database/test_service.py` passes (25 tests), including `test_restricted_case_filter_with_test_data`.

**Test status:** the full suite gives 361 passed, 7 failed, 4 skipped. The 7 failures are in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They also fail on the unmodified code, and I did not investigate them.

**Not committed:** the changes are in the working tree only.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc7