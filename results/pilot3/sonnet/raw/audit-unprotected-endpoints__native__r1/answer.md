Five data-changing routes across the two files declare no `PermissionsDependency` in their route definition. I checked each decorator in both `views.py` files.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""`
- `create_case_channel`: `POST /{case_id}/resources/conversation`
- `create_case_resources`: `POST /{case_id}/resources`

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`: `POST ""`
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`. The matching case handler does declare a permission, and so do the other incident event routes.

All other POST, PUT, PATCH and DELETE routes in both files declare a `PermissionsDependency`. I only looked at the route definitions in these two files, so any router-level or app-level dependency applied elsewhere is not counted.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event