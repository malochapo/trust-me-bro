Five data-changing routes declare no `PermissionsDependency` in their route definition. I checked this by listing every route decorator in both files and looking for the dependency on each POST, PUT, PATCH and DELETE route. I then read the five hits that had no `dependencies=` line in their decorators.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""`
- `create_case_channel`: `POST /{case_id}/resources/conversation`
- `create_case_resources`: `POST /{case_id}/resources`

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`: `POST ""`
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`

Every other POST, PUT, PATCH and DELETE route in both files declares a `PermissionsDependency`.

I only checked the route definitions. Authentication or other access checks applied elsewhere, such as at the router level, would not show up here.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event