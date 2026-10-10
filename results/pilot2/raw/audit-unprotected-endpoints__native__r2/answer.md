Five data-changing routes in these two files have no `PermissionsDependency` in their route definition. I checked each route decorator in both files. Of the three routes whose decorators had no `dependencies=` line in the grep output, I read the decorators of `create_case_channel`, `create_case_resources` and `incident.delete_custom_event`. I didn't check whether permissions are enforced elsewhere, such as in the handler body, a router-level dependency or middleware.

**Case API (`src/dispatch/case/views.py`)**
- `create_case` — `POST ""`
- `create_case_channel` — `POST /{case_id}/resources/conversation`
- `create_case_resources` — `POST /{case_id}/resources`

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident` — `POST ""`
- `delete_custom_event` — `DELETE /{incident_id}/event/{event_uuid}`. This one stands out because the matching case route, and the other incident event routes, all require an event permission.

The unprotected GET routes (`get_cases`, `get_cases_minimal`, `get_incidents`, `get_incident_forecast`) don't change data, so I left them out.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event