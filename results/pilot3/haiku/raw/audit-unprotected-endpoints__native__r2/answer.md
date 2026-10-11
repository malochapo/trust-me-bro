Five mutating handlers have no `PermissionsDependency` in their route definition: three in the case API and two in the incident API. I checked every POST, PUT, PATCH and DELETE decorator in both files. Neither file sets router-level dependencies or registers routes another way, so the per-route check is complete.

**Case API (`src/dispatch/case/views.py`)**
- `create_case` (`POST ""`, line 162)
- `create_case_channel` (`POST /{case_id}/resources/conversation`, line 236)
- `create_case_resources` (`POST /{case_id}/resources`, line 260)

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident` (`POST ""`, line 117)
- `delete_custom_event` (`DELETE /{incident_id}/event/{event_uuid}`, line 503)

`create_incident_resources` (line 163) is excluded because it declares `PermissionsDependency([IncidentViewPermission])`. That is a weak check for a write route, since it requires view rather than edit permission, but it is declared, so it falls outside what you asked for.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event