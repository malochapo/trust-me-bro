**Unprotected mutating routes (no `PermissionsDependency` on the route):**

**Case API** (`src/dispatch/case/views.py`)
- `POST ""`: `create_case` (line 162)
- `POST /{case_id}/resources/conversation`: `create_case_channel` (line 236)
- `POST /{case_id}/resources`: `create_case_resources` (line 260)

**Incident API** (`src/dispatch/incident/views.py`)
- `POST ""`: `create_incident` (line 117)
- `DELETE /{incident_id}/event/{event_uuid}`: `delete_custom_event` (line 503)

I checked only route-level `dependencies=` on each decorator, as the question asks. I did not check router-level dependencies on the `APIRouter` objects, and I did not check whether the functions enforce permissions internally.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event