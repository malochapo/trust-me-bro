Five write routes have no `PermissionsDependency` in their route definition:

- `case.create_case`: `POST ""` (`src/dispatch/case/views.py:162`)
- `case.create_case_channel`: `POST /{case_id}/resources/conversation` (`src/dispatch/case/views.py:236`)
- `case.create_case_resources`: `POST /{case_id}/resources` (`src/dispatch/case/views.py:260`)
- `incident.create_incident`: `POST ""` (`src/dispatch/incident/views.py:117`)
- `incident.delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}` (`src/dispatch/incident/views.py:503`)

Neither router sets router-level dependencies (`APIRouter()` at `case/views.py:61` and `incident/views.py:59`), so these handlers have no permission check at the route level.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event