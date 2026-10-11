Five handlers that change data have no `PermissionsDependency` in their route definition. I checked the decorators in both files and read the bodies of the ones that looked bare.

**Case API (`src/dispatch/case/views.py`)**
- `create_case`: `POST ""`.
- `create_case_channel`: `POST /{case_id}/resources/conversation`.
- `create_case_resources`: `POST /{case_id}/resources`.

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident`: `POST ""`.
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`. The case-side equivalent is protected, so this one looks like an omission.

Every other POST, PUT, PATCH and DELETE route in both files declares a `PermissionsDependency`. Both routers are plain `APIRouter()` with no router-level dependencies. A dependency attached where the router is included (for example in `api.py`) would not show up here, and I did not check that.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event