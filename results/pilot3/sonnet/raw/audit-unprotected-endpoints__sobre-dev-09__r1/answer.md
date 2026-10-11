Four data-changing routes declare no `PermissionsDependency`. Both routers are plain `APIRouter()` with no router-level dependency, so nothing else covers them.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""`, line 162.
- `create_case_channel`: `POST /{case_id}/resources/conversation`, line 236.
- `create_case_resources`: `POST /{case_id}/resources`, line 260.

**Incident API (`src/dispatch/incident/views.py`)**
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`, line 503.
- `create_incident` (`POST ""`, line 117) also has no `PermissionsDependency`, so it belongs in the list as well.

The incident file has five unprotected writes, not four: `create_incident` and `delete_custom_event`. I miscounted above, so here is the corrected total of five handlers:

- case: `create_case`, `create_case_channel`, `create_case_resources`
- incident: `create_incident`, `delete_custom_event`

The GET routes `get_cases`, `get_cases_minimal`, `get_incidents` and `get_incident_forecast` also lack the dependency. They only read data, so they are outside your scope.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event