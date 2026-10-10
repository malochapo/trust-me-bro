Five data-changing routes in these two files have no `PermissionsDependency` in their route definition. I read each decorator to confirm.

**Case API (`case/views.py`)**
- `create_case`: `POST ""`
- `create_case_channel`: `POST /{case_id}/resources/conversation`
- `create_case_resources`: `POST /{case_id}/resources`

**Incident API (`incident/views.py`)**
- `create_incident`: `POST ""`
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`

`delete_custom_event` is the odd one out. Its case counterpart and the other incident event routes all use an event permission, but this route has none.

I only checked the route definitions, as asked. I did not look for router-level dependencies where the routers are mounted.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event