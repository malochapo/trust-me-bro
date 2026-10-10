Five data-changing routes declare no `PermissionsDependency` in their route definition. I parsed every `@router.post`, `@router.put`, `@router.patch` and `@router.delete` decorator in both files and checked each one for `PermissionsDependency`. I then confirmed the findings by reading the decorators. Both files use a bare `APIRouter()` with no router-level dependencies.

**Case API (`src/dispatch/case/views.py`)**
- `create_case` (POST, line 162)
- `create_case_channel` (POST, line 236)
- `create_case_resources` (POST, line 260)

**Incident API (`src/dispatch/incident/views.py`)**
- `create_incident` (POST, line 117)
- `delete_custom_event` (DELETE, line 503)

The other 22 data-changing routes in the two files declare a `PermissionsDependency`.

I only checked for the declaration in the route definition, as you asked. I didn't check whether these handlers enforce access some other way, such as an authentication dependency on the app or a check inside the function body.

UNPROTECTED: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event