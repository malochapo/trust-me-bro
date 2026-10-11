Three case handlers and two incident handlers change data without a `PermissionsDependency` on their route.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""` (line 162)
- `create_case_channel`: `POST /{case_id}/resources/conversation` (line 236)
- `create_case_resources`: `POST /{case_id}/resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`: `POST ""` (line 117)
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}` (line 503)

Every other POST, PUT, PATCH and DELETE route in both files declares a `PermissionsDependency` in its decorator. `create_incident_resources` declares `IncidentViewPermission`, so I excluded it. Both routers are mounted in `src/dispatch/api.py` (the case router at line 191) with no router-level permission dependency that I could find. I did not check the authentication dependencies on the parent router.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event