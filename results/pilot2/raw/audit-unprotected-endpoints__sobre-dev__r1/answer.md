Five data-changing routes in the two files have no `PermissionsDependency` in their route definition:

**Case API (`case/views.py`)**
- `create_case`: `POST ""`, line 162.
- `create_case_channel`: `POST /{case_id}/resources/conversation`, line 236.
- `create_case_resources`: `POST /{case_id}/resources`, line 260.

**Incident API (`incident/views.py`)**
- `create_incident`: `POST ""`, line 117.
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`, line 503. It has no dependency even though the matching create, update and export event routes use `IncidentEventPermission`.

I read the route decorators directly. Every other POST, PUT, PATCH and DELETE route in both files declares a `PermissionsDependency`.

I did not check whether these routes are protected some other way, for example by router-level dependencies where the router is included, or by checks inside the handler bodies.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event