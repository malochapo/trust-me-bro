Six data-changing routes (POST, PUT, PATCH or DELETE) have no `PermissionsDependency` in their route definition. I checked each route decorator in both files. Neither router sets a router-level dependency: both use a bare `APIRouter()`.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""`, line 162.
- `create_case_channel`: `POST /{case_id}/resources/conversation`, line 236.
- `create_case_resources`: `POST /{case_id}/resources`, line 260.

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`: `POST ""`, line 117.
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`, line 503.
- `add_participant_to_incident` is protected, so it isn't listed.

The GET routes `generate_tactical_report` and `generate_summary` do have a permission check, but they don't change data, so they're out of scope. Several other GET routes have no check either (`get_cases`, `get_cases_minimal`, `get_incidents` and `get_incident_forecast`). They only read data, so I left them out too.

I only checked the route definitions. A handler could still do its own permission check inside its body, which I didn't look for.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event