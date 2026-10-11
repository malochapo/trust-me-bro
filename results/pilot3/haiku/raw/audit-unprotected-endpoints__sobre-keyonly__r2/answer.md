Five mutating handlers have no `PermissionsDependency` in their route definitions. Neither router has router-level dependencies, so these are the only gaps.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""`
- `create_case_channel`: `POST /{case_id}/resources/conversation`
- `create_case_resources`: `POST /{case_id}/resources`

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`: `POST ""`
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`

I left out `generate_summary` (`/{incident_id}/regenerate`) because it is a `GET` route, even though it changes data. The other handlers that look similar are declared: `create_incident_resources` uses `IncidentViewPermission`, which is a weak check for a write, but it is declared.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event