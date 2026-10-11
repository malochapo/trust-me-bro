Five mutating routes have no `PermissionsDependency` in their route definition. Each one is a bare `@router.post`/`@router.delete` decorator with no `dependencies=[...]` argument, and neither router is built with router-level dependencies (`APIRouter()` in both files).

- `case.create_case` (`src/dispatch/case/views.py:162`), POST `""`
- `case.create_case_channel` (`src/dispatch/case/views.py:236`), POST `/{case_id}/resources/conversation`
- `case.create_case_resources` (`src/dispatch/case/views.py:260`), POST `/{case_id}/resources`
- `incident.create_incident` (`src/dispatch/incident/views.py:117`), POST `""`
- `incident.delete_custom_event` (`src/dispatch/incident/views.py:503`), DELETE `/{incident_id}/event/{event_uuid}`

The check was literal: it looks only for a `PermissionsDependency` in the route definition. Any authentication applied elsewhere, such as middleware or the `CurrentUser`/`CurrentCase`/`CurrentIncident` dependencies, is not counted.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event