Six routes change data without a `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
3. `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

That's five. The sixth is the `create_case_channel` already counted above, so the list has five entries, not six. I found no router-level dependencies: both files create a bare `APIRouter()`, so these routes have no protection from their route definitions. No code was changed.

----- next turn -----

The regression was in commit `28c21e1e` (2025-07-14, "refactor(incident): tidy custom event routes"). It removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from `delete_custom_event` (`DELETE /{incident_id}/event/{event_uuid}`). Since that commit, anyone authenticated could delete a timeline event on any incident.

The other candidates are not regressions. `create_case_channel` and `create_case_resources` were added without a permission in their introducing commits (`ced74f33`, `f08a22b3`). Commit `328359b5` changed incident event routes to `IncidentEventPermission` on purpose, and that's why this route had the check at all.

**Changes**
- `src/dispatch/incident/views.py`: restored the `IncidentEventPermission` dependency on `delete_custom_event`.
- `tests/incident/test_incident_views.py` (new): checks that the `DELETE /{incident_id}/event/{event_uuid}` route on the incident router still declares `IncidentEventPermission`. It inspects the route definition rather than calling the view, because the existing tests call view functions directly, and that bypasses route dependencies.

**Verification**
- With the fix: `python -m pytest tests/incident/test_incident_views.py` passes (1 passed).
- With the fix stashed: the same test fails, so it catches the removal.

I did not run the full suite. I left the three other unprotected create/report routes unchanged, since you said they are open by design.

----- next turn -----

The cases list now hides restricted cases that a non-admin user doesn't participate in. The bug was introduced in commit `42699ebc` (2025-09-02, "refactor(database): flatten the restricted case filter").

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` lets any non-admin see every restricted case. Before the refactor, the restricted branch was grouped with the participant-email check in an `and_`. The refactor flattened it into the `or_`, so the email check no longer applied to restricted cases. The earlier commit `b05613b5` (sec(authz), #6155) had the correct form.

**Fix:** I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` grouping, matching the incident filter. The fix is in `src/dispatch/database/service.py`.

**Verification:**
- Before the fix, `tests/database/test_service.py -k restricted` failed with `Member should see 3 cases ... got 4`.
- After the fix, `tests/database/test_service.py` and `tests/case/test_case_service.py` pass (35 passed).

I didn't change any tests. I also didn't run the full suite.

----- next turn -----

**Review recap**

- **Unprotected write routes (before changes):** five routes in the case and incident views had no `PermissionsDependency`. Three are open by design: `create_case`, `create_incident`, and `create_case_resources`/`create_case_channel`, which you confirmed are intentional. Wait, that is four: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`. The fifth is `delete_custom_event`, which is the regression below. I did not change the open-by-design routes.
- **Regression restored:** `delete_custom_event` in `src/dispatch/incident/views.py` had lost its `IncidentEventPermission` check in `28c21e1e` (2025-07-14, "refactor(incident): tidy custom event routes"). I restored it and added `tests/incident/test_incident_views.py`, which fails if the check is removed again. It fails without the fix and passes with it.
- **Visibility bug fixed:** `restricted_case_filter` in `src/dispatch/database/service.py` let non-admins see every restricted case. This came from `42699ebc` (2025-09-02, "refactor(database): flatten the restricted case filter"), which removed the participant check from the restricted branch. I restored the check. The existing test `test_restricted_case_filter_with_test_data` failed before the fix (4 cases instead of 3) and passes now, along with the other database and case service tests (35 passed).

I did not run the full test suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc