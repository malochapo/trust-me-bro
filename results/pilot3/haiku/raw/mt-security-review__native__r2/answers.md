Five endpoints change data without a `PermissionsDependency` in their route definition:

1. `src/dispatch/case/views.py:162` — `POST ""` (`create_case`)
2. `src/dispatch/case/views.py:236` — `POST /{case_id}/resources/conversation` (`create_case_channel`)
3. `src/dispatch/case/views.py:260` — `POST /{case_id}/resources` (creates resources for an existing case)
4. `src/dispatch/incident/views.py:117` — `POST ""` (`create_incident`)
5. `src/dispatch/incident/views.py:503` — `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`)

I checked each POST/PUT/PATCH/DELETE decorator block in both files. The other 27 mutating routes declare a `PermissionsDependency` in their `dependencies=[...]`. Neither file sets router-level dependencies, since each has a plain `APIRouter()`. The route-level check ignores any `Depends` in function parameters, and it doesn't account for protection applied elsewhere, such as middleware. I haven't changed any code.

----- next turn -----

Only one of the five is a regression: the incident `DELETE /{incident_id}/event/{event_uuid}` route. I restored its check and added a test that fails if it goes missing again. Nothing is committed.

**The regression**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed the `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line. It was a one-line deletion, and the commit message describes a refactor, not a permission change.
- The sibling routes for creating, updating and exporting custom events still have the check.

**Not a removal regression**
- The case endpoints `POST /{case_id}/resources/conversation` and `POST /{case_id}/resources` were added in `ced74f33` and `f08a22b3` without any `PermissionsDependency`. No commit removed one, so the missing check is an original gap rather than a regression. I didn't change them. Tell me if they should require a permission, and which one.
- `POST ""` on cases and incidents are the open-by-design creates you mentioned.

**Changes**
- `src/dispatch/incident/views.py:506`: restored the `dependencies` line on the delete route.
- `tests/incident/test_incident_views_permissions.py` (new): finds the DELETE route on the incident router and asserts `IncidentEventPermission` is among its `PermissionsDependency` classes. It inspects route definitions rather than making HTTP calls, so it doesn't depend on auth setup.

**Verification**
- With the fix, the new test passes.
- With the HEAD version of `views.py` swapped in, the test fails, which shows it catches the regression. I restored the fixed file afterwards.
- `python -m pytest tests/case/test_case_event_views.py tests/incident/test_incident_views_permissions.py`: 5 passed.
- I didn't run the full suite.

----- next turn -----

The cause is in `restricted_case_filter` in `src/dispatch/database/service.py`. It is the filter that decides which cases a non-admin user can see in the cases list.

**Cause:** the filter's OR condition had lost its `and_(...)` wrapper, so it read:
```python
Case.visibility == Visibility.open,
Case.visibility == Visibility.restricted,   # any restricted case passes
IndividualContact.email == current_user.email,
```
Any restricted case matched for any non-admin user, whether or not they were a participant. The incident filter keeps the correct form.

**Introducing commit:** `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). The commit message calls it a refactor, but it changed the logic. The `and_` wrapper that tied restricted visibility to participation was removed. The wrapper itself dates from `b05613b5` (the authz hardening commit), which had the correct form.

**Fix:** restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` grouping, matching the incident filter. No tests were changed.

**Verification:**
- `tests/database/test_service.py` and `tests/case/test_case_service.py`: 35 passed.
- Against the buggy HEAD version, `test_restricted_case_filter_with_test_data` fails: the member sees 4 cases where the test expects 3. So the existing test catches this bug.

The working tree also still contains the earlier `delete_custom_event` permission restore from the previous task. Nothing is committed.

----- next turn -----

## Review recap

**Permission gaps on data-changing routes.** Five POST/PUT/PATCH/DELETE handlers had no `PermissionsDependency` in their route definitions:
- `case.create_case`: open by design (anyone may report a case).
- `incident.create_incident`: open by design (anyone may report an incident).
- `case.create_case_channel` and `case.create_case_resources`: never had a check. They were added in `ced74f33` and `f08a22b3` without one, so this is an original gap, not a removal. I left them unchanged; they need a decision on which permission they should require.
- `incident.delete_custom_event`: a regression.

**Regression fixed.** `delete_custom_event` lost its `IncidentEventPermission` check in `28c21e1e`, a commit titled "refactor(incident): tidy custom event routes" that deleted only that one line. I restored the line in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views_permissions.py`. The new test fails on the HEAD version and passes with the fix. The existing `tests/case/test_case_event_views.py` tests still pass.

**Visibility bug fixed.** `restricted_case_filter` in `src/dispatch/database/service.py` lost its `and_(...)` wrapper, so any restricted case matched for any non-admin user. The fix restores the wrapper to match the incident filter. The existing tests, which were not changed, fail on the buggy version and pass with the fix (35 passed across the database and case service tests).

Nothing is committed. Both fixes are in the working tree, and I did not run the full test suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc