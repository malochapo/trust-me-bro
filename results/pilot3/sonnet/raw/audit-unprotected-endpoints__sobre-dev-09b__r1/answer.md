Four data-changing routes in these two files declare no `PermissionsDependency` in their route definition. I read the route decorators in both files and checked the three that weren't clear from a first pass.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""`.
- `create_case_channel`: `POST /{case_id}/resources/conversation`.
- `create_case_resources`: `POST /{case_id}/resources`.

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`: `POST ""`.
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`. Its sibling event routes (`create_custom_event`, `update_custom_event`, `export_timeline_event`) use `IncidentEventPermission`, so this one looks like an oversight.

Every other POST, PUT, PATCH and DELETE route in both files has a `PermissionsDependency`. The GET routes without one are read-only, so I left them out as you asked.

I only checked the decorators. A route could still enforce access inside its function body, or through a router-level dependency set where the router is included. I didn't look for either.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event