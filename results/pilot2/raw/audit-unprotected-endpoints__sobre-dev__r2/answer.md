Four data-changing routes in these two files have no `PermissionsDependency` in their route definition. I checked each route decorator in `case/views.py` and `incident/views.py`. Every other POST, PUT, PATCH and DELETE route declares one.

**Case API**
- `create_case` (POST `""`) has no permissions dependency.
- `create_case_channel` (POST `/{case_id}/resources/conversation`) has none. It creates a dedicated conversation channel and adds the case participants to it.
- `create_case_resources` (POST `/{case_id}/resources`) has none.

**Incident API**
- `create_incident` (POST `""`) has no permissions dependency.
- `delete_custom_event` (DELETE `/{incident_id}/event/{event_uuid}`) has none. The matching case handler is protected with `CaseEventPermission`, and the other incident event routes use `IncidentEventPermission`, so this one looks like an omission.

I did not check whether any of these are protected some other way, such as a router-level dependency. The question was about the route definition itself.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event