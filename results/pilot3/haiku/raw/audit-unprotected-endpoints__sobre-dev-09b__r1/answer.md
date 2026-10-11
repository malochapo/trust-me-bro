Five mutating routes have no `PermissionsDependency` in their route definition. Neither router sets dependencies at the `APIRouter` level, so nothing protects them globally.

- `src/dispatch/case/views.py:162`: `POST ""` → `create_case`
- `src/dispatch/case/views.py:236`: `POST /{case_id}/resources/conversation` → `create_case_channel`
- `src/dispatch/case/views.py:260`: `POST /{case_id}/resources` → `create_case_resources`
- `src/dispatch/incident/views.py:117`: `POST ""` → `create_incident`
- `src/dispatch/incident/views.py:503`: `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event`

All other POST, PUT, PATCH and DELETE routes in both files declare a `PermissionsDependency`. The check is based on the route decorators only. I did not read the handler bodies, so an authorization check done inside a function would not show up here.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event