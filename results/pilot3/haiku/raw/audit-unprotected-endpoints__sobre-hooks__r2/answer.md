Five handlers change data without a `PermissionsDependency` on their route. Three are in the case API and two in the incident API.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""` (line 162)
- `create_case_channel`: `POST /{case_id}/resources/conversation` (line 236)
- `create_case_resources`: `POST /{case_id}/resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`: `POST ""` (line 117)
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}` (line 503)

Neither router sets a router-level permission. The case router is mounted under `authenticated_organization_api_router`, whose only dependency is `get_organization_path`, which resolves the organization and is not a permission check. Every other mutating route in both files declares a `PermissionsDependency`.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event