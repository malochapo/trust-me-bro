Four data-changing routes in these two files have no `PermissionsDependency` in their route definition. I checked each route decorator in both `views.py` files. Every other POST, PUT, PATCH and DELETE route declares one.

**Case API**
- `create_case` — `POST ""`, creates a case.
- `create_case_channel` — `POST /{case_id}/resources/conversation`, creates the conversation channel for an existing case.
- `create_case_resources` — `POST /{case_id}/resources`, creates resources for an existing case.

**Incident API**
- `create_incident` — `POST ""`, creates an incident.
- `delete_custom_event` — `DELETE /{incident_id}/event/{event_uuid}`, deletes a custom event. This is the notable one. The matching case route and the other incident event routes are all protected.

The incident API has no other unprotected data-changing route.

I didn't check whether these routes are protected some other way, such as at router-include level or in the authentication layer. This covers only what's declared in the route definitions, as you asked.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event