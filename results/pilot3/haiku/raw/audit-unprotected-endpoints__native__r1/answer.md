Five write routes have no `PermissionsDependency` in their route definition. I checked the decorators in both files, and neither router sets router-level `dependencies`, so there is no blanket protection to account for.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`, `POST ""` (line 162): no `dependencies`.
- `create_case_channel`, `POST /{case_id}/resources/conversation` (line 236): no `dependencies`.
- `create_case_resources`, `POST /{case_id}/resources` (line 260): no `dependencies`.

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`, `POST ""` (line 117): no `dependencies`.
- `delete_custom_event`, `DELETE /{incident_id}/event/{event_uuid}` (line 503): no `dependencies`.

The other write routes in both files declare a permission. This includes `incident.create_incident_resources`, which requires `IncidentViewPermission`, a weaker check than the edit permission used elsewhere. I left it out because it does declare a dependency.

The check is only on the route definition. Some handlers may enforce authorization inside the function body, for example through `current_user` or organization scoping, and I did not review that.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event