Five mutating routes have no `PermissionsDependency` in their route definition.

**Case API (`case/views.py`)**
- `create_case`: `POST ""`
- `create_case_channel`: `POST /{case_id}/resources/conversation`
- `create_case_resources`: `POST /{case_id}/resources`

**Incident API (`incident/views.py`)**
- `create_incident`: `POST ""`
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`. Its sibling event routes (create, update, export) all require `IncidentEventPermission`, so this one looks like an omission.

I checked only the route decorators. I did not check whether a router-level dependency is applied where the routers are mounted (for example in `api.py`). I also did not check whether any of these handlers enforce access inside the function body.

The GET routes `generate_tactical_report` and `generate_summary` do declare permissions, and they don't change data through a POST, PUT, PATCH or DELETE route anyway.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event