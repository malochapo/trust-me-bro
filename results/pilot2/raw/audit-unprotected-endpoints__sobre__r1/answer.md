Of the 27 data-changing routes (POST, PUT, PATCH or DELETE) in the two files, 5 have no `PermissionsDependency` in their route definition. I parsed the route decorators with a script to find them. The other 22 declare one.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""`
- `create_case_channel`: `POST /{case_id}/resources/conversation`
- `create_case_resources`: `POST /{case_id}/resources`

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`: `POST ""`
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`

`delete_custom_event` stands out because the case API's equivalent route is protected.

I only checked the decorators. I did not check whether these handlers enforce access some other way, such as a dependency in the function signature or a router-level dependency.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event