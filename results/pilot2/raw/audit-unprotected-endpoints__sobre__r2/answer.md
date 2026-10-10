Five data-changing routes declare no `PermissionsDependency` in their route definition. I parsed the decorators in both files with Python's `ast` module and checked each POST, PUT, PATCH and DELETE route for `PermissionsDependency`. I then read the surrounding source for the five hits.

**Case API (`src/dispatch/case/views.py`)**
- `create_case` (POST `""`)
- `create_case_channel` (POST `/{case_id}/resources/conversation`)
- `create_case_resources` (POST `/{case_id}/resources`)

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident` (POST `""`)
- `delete_custom_event` (DELETE `/{incident_id}/event/{event_uuid}`)

The incident `delete_custom_event` stands out because its case counterpart does declare `CaseEventPermission`. Both files use a plain `APIRouter()` with no `api_route`/`add_api_route` calls. I did not check whether a router-level dependency is attached where the routers are included, so a permission could still apply there.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event