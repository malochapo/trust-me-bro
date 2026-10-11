Five mutating routes have no `PermissionsDependency` in their route definition:

- **`case/views.py`:**
  - `create_case` (`POST ""`, line 162)
  - `create_case_channel` (`POST /{case_id}/resources/conversation`, line 236)
  - `create_case_resources` (`POST /{case_id}/resources`, line 260)
- **`incident/views.py`:**
  - `create_incident` (`POST ""`, line 117)
  - `delete_custom_event` (`DELETE /{incident_id}/event/{event_uuid}`, line 503)

The other POST, PUT, PATCH and DELETE routes in both files declare a `PermissionsDependency`. Neither router is built with router-level dependencies (`APIRouter()` at case/views.py:61 and incident/views.py:59), so the check is per-route. The case routes that call `CurrentCase` but have no dependency are `create_case_channel` and `create_case_resources`. `create_incident_resources` declares `IncidentViewPermission`, a weaker check than the edit permissions used elsewhere, so I left it out of the list.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event