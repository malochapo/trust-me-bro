Five mutating routes have no `PermissionsDependency` in their route definition:

- **Case API** (`src/dispatch/case/views.py`):
  - `create_case`, `POST ""` (line 162)
  - `create_case_channel`, `POST /{case_id}/resources/conversation` (line 236)
  - `create_case_resources`, `POST /{case_id}/resources` (line 260)
- **Incident API** (`src/dispatch/incident/views.py`):
  - `create_incident`, `POST ""` (line 117)
  - `delete_custom_event`, `DELETE /{incident_id}/event/{event_uuid}` (line 503)

Every other POST, PUT, PATCH and DELETE route in both files declares a `PermissionsDependency` in its decorator. I read the multi-line decorators directly to confirm the absence on these five.

One note outside the criteria: `create_incident_resources` (incident, line 163) does declare a dependency, but it is `IncidentViewPermission`, a view-level check on a route that creates resources. You may want to look at whether that is the intended level.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event