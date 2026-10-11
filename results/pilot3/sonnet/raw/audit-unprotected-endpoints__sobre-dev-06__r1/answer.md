Five data-changing routes (POST, PUT, PATCH or DELETE) have no `PermissionsDependency` in their route definition. I read the decorators in both files and checked the three multi-line ones directly.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""`.
- `create_case_channel`: `POST /{case_id}/resources/conversation`.
- `create_case_resources`: `POST /{case_id}/resources`.

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`: `POST ""`.
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`. Its sibling event routes (`create_custom_event`, `update_custom_event`, `export_timeline_event`) all declare `IncidentEventPermission`, so this one stands out.

I only checked the route decorators, as you asked. A handler could still enforce access in its function body or through a router-level dependency, and I did not look for either.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event