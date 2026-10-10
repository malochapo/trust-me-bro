Five data-changing routes in the two files declare no `PermissionsDependency` in their route definition. I checked every POST, PUT, PATCH and DELETE decorator in both files.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""`, line 162.
- `create_case_channel`: `POST /{case_id}/resources/conversation`, line 236.
- `create_case_resources`: `POST /{case_id}/resources`, line 260.

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`: `POST ""`, line 117.
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`, line 503. The matching case route, `case.delete_custom_event`, does declare `CaseEventPermission`.

I only checked the route definitions. A handler could still enforce access some other way, such as a check inside its body or a router-level dependency. I did not look for either.

The `GET` routes are read-only, so I left them out.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event