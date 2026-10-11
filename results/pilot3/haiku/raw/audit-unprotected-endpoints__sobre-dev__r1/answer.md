Eight mutating routes in the two files have no `PermissionsDependency` in their decorator. Both routers are plain `APIRouter()` instances with no router-level dependencies, so nothing is inherited.

**Case API (`src/dispatch/case/views.py`)**
- `POST ""` → `create_case` (line 162)
- `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
- `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
- `POST ""` → `create_incident` (line 117)
- `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

Outside the list: `create_incident_resources` (`POST /{incident_id}/resources`) is guarded, but by `IncidentViewPermission` rather than an edit permission. That may be intentional, but it means a view-only role can create incident resources.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event