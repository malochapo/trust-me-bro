Five handlers that change data have no `PermissionsDependency` in their route definition. I found them with a script that checks every `@router.post/put/patch/delete` decorator in both files. Apart from the `@router.get/post/put/patch/delete` routes, neither file has any other decorators.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""`
- `create_case_channel`: `POST /{case_id}/resources/conversation`
- `create_case_resources`: `POST /{case_id}/resources`

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`: `POST ""`
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`. This one takes a `current_user` argument but declares no permission check, and it schedules `event_flows.delete_incident_event`.

I judged "declared in the route definition" by the decorator only. I did not read the bodies of the other handlers, so a handler that checks permissions some other way would still count as protected here.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event