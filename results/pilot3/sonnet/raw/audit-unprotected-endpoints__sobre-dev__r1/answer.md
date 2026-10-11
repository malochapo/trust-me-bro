Five of the case and incident data-changing routes have no `PermissionsDependency` in their decorator. Four more have no `dependencies=` list at all. I checked the `@router` decorators in both files. I did not check whether `api.py` adds a dependency when it includes the routers, because you asked about the route definitions.

**Case API (`src/dispatch/case/views.py`)**
- `create_case` (`POST ""`)
- `create_case_channel` (`POST /{case_id}/resources/conversation`)
- `create_case_resources` (`POST /{case_id}/resources`)

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident` (`POST ""`)
- `delete_custom_event` (`DELETE /{incident_id}/event/{event_uuid}`)

The incident `delete_custom_event` route stands out. Its sibling event routes (create, update, export) all require `IncidentEventPermission`, and this one has none.

All other POST, PUT, PATCH and DELETE routes in both files declare a `PermissionsDependency`.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event