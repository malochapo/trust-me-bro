Five write routes have no `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
- `POST ""` → `create_case` (line 162)
- `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
- `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
- `POST ""` → `create_incident` (line 117)
- `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

All other POST, PUT, PATCH and DELETE routes in both files declare a `PermissionsDependency`. The routers themselves (`APIRouter()` at case/views.py:61 and incident/views.py:59) add no router-level dependencies. I only checked the route definitions, not `api.py` or middleware, so a guard applied elsewhere would not show here.

Not in the list because it declares a dependency: `incident.create_incident_resources` (incident/views.py:163) is a POST guarded only by `IncidentViewPermission`, which is weaker than the edit permission used for the other incident writes.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event