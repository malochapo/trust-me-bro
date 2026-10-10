Four data-changing routes declare no `PermissionsDependency` in their route definition. I checked each route's decorator in both files. Every other POST, PUT, PATCH and DELETE route declares one.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""`, creates a case.
- `create_case_channel`: `POST /{case_id}/resources/conversation`, creates the conversation channel for an existing case.
- `create_case_resources`: `POST /{case_id}/resources`, creates resources for an existing case.

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`: `POST ""`, creates an incident.
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`, deletes a custom event.

`delete_custom_event` is the notable gap. Its case counterpart is protected by `CaseEventPermission`, and the other incident event routes use `IncidentEventPermission`.

I only looked at the route definitions. I didn't check whether these handlers enforce access some other way, such as a router-level dependency or a check inside the function body.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event