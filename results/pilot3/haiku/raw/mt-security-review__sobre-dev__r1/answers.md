Five routes change data without a `PermissionsDependency` in their decorator:

**Incident API (`src/dispatch/incident/views.py`)**
1. `POST ""`: `create_incident`, line 117
2. `DELETE "/{incident_id}/event/{event_uuid}"`: `delete_custom_event`, line 503

**Case API (`src/dispatch/case/views.py`)**
3. `POST ""`: `create_case`, line 162
4. `POST "/{case_id}/resources/conversation"`: `create_case_channel`, line 236
5. `POST "/{case_id}/resources"`: `create_case_resources`, line 260

Neither router sets router-level dependencies (`APIRouter()` with no arguments in both files), so these five are unprotected at the route level. I only checked the route definitions, as you asked. Some of these functions may still do authorization checks inside the body, and I did not review that.

No code was changed.

----- next turn -----

The regression was in the incident API, and it is restored with a test that fails when the check is missing.

**The regression:** `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`). Commit `28c21e1e` ("refactor(incident): tidy custom event routes") deleted its `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line. The commit message does not mention a permission change. The other custom event routes in that file still have the check.

The two case resource routes (`create_case_channel` and `create_case_resources`) never had a check. `f08a22b3` added them without one, so I treated them as a design gap rather than a regression. I did not change them. The three you said are open by design, `create_case` and `create_incident` plus the case `create_case_channel`, were left alone as well.

**Changes:**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on the delete route.
- `tests/incident/test_incident_custom_event_permissions.py` (new): finds the DELETE route on the incident router and asserts `IncidentEventPermission` is among its `PermissionsDependency` classes. I ran it with and without the fix. It passes with the fix and fails without it.

**Test suite:** `python -m pytest` gives 360 passed, 8 failed, 4 skipped. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. They fail the same way with my change stashed, so they predate this work. I did not investigate them.

Nothing is committed.

----- next turn -----

The cases list leaked restricted cases to members who were not participants. The cause is in `restricted_case_filter` in `src/dispatch/database/service.py`, and it is fixed.

**Cause:** commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sep 2 2025, Sam Ortega) introduced it. Before that commit the filter was:

```python
or_(
    Case.visibility == Visibility.open,
    and_(
        Case.visibility == Visibility.restricted,
        IndividualContact.email == current_user.email,
    ),
)
```

The refactor removed the `and_`, which left `Case.visibility == Visibility.restricted` as a standalone `OR` term. Every restricted case then matched for every non-admin user. The incident version of the filter still has the correct grouping.

**Fix:** I restored the `and_(...)` grouping in `restricted_case_filter`. No tests were changed.

**Verification:**
- `tests/database/test_service.py`: 25 passed. `test_restricted_case_filter_with_test_data` was failing before the fix and passes now.
- Full `python -m pytest`: 361 passed, 7 failed, 4 skipped. The 7 failures are in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py`. They also fail without my changes, so they predate this work and I did not investigate them.

Earlier in this session I also restored the `IncidentEventPermission` check on the incident custom event delete route and added a test for it (`tests/incident/test_incident_custom_event_permissions.py`). Nothing is committed.

----- next turn -----

## Review recap

**1. Unprotected data-changing routes.** Five POST/PUT/PATCH/DELETE handlers had no `PermissionsDependency` in their route definition. `create_incident` and `create_case` are open by design, since anyone may report. The other three are described below.

**2. Regression: incident custom event delete.** `DELETE /incident/{incident_id}/event/{event_uuid}` lost its `IncidentEventPermission` check in commit `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored the check in `src/dispatch/incident/views.py`. I added `tests/incident/test_incident_custom_event_permissions.py`, which passes with the fix and fails without it.

**3. Case resource routes.** `create_case_channel` and `create_case_resources` never had a check, since they were added without one (`ced74f33` and `f08a22b3`). I did not add one, because the request was only to restore a removed check. This is a decision for you.

**4. Restricted cases visible to members.** `restricted_case_filter` in `src/dispatch/database/service.py` let every restricted case match for non-admin users. Commit `42699ebc` removed the `and_` that tied restricted visibility to participation. I restored the grouping. `tests/database/test_service.py` now passes (25 tests), and the existing tests were not changed.

**Test suite:** 361 passed, 7 failed, 4 skipped. The 7 failures are in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py`. They fail the same way without my changes, so they predate this work, and I did not investigate them.

Nothing is committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc