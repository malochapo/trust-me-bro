Five data-changing routes (POST, PUT, PATCH or DELETE) have no `PermissionsDependency` in their route definition. I read the decorators in both files. I did not check whether the router or the app applies a permission check elsewhere.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""`.
- `create_case_channel`: `POST /{case_id}/resources/conversation`.
- `create_case_resources`: `POST /{case_id}/resources`.

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`: `POST ""`.
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`. Its sibling event routes (create, update, export) all declare `IncidentEventPermission`, so this one looks like an omission.

All other POST, PUT, PATCH and DELETE routes in the two files declare a `PermissionsDependency`. The remaining routes without one are GET routes, which don't change data.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event