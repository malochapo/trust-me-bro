Five data-changing routes in these two files have no `PermissionsDependency` in their route definition. I checked each route decorator in `case/views.py` and `incident/views.py`. For the five below I also read the full definition to confirm no dependency is declared.

**Case API**
- `create_case` (`POST ""`)
- `create_case_channel` (`POST /{case_id}/resources/conversation`)
- `create_case_resources` (`POST /{case_id}/resources`)

**Incident API**
- `create_incident` (`POST ""`)
- `delete_custom_event` (`DELETE /{incident_id}/event/{event_uuid}`). This one is the notable gap. Its sibling event routes (create, update, export) all require `IncidentEventPermission`, but the delete route has no permission check.

I did not check whether authentication or other protection is applied at the router or app level. This list only covers what the route definitions themselves declare.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event