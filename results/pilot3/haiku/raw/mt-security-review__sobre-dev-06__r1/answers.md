Five mutating routes have no `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` (create_case), line 162
2. `POST /{case_id}/resources/conversation`, line 236
3. `POST /{case_id}/resources`, line 260

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` (create_incident), line 117
5. `DELETE /{incident_id}/event/{event_uuid}` (delete_custom_event), line 503

I checked every `@router.post/put/patch/delete` decorator in both files, including multi-line ones, and confirmed that neither `APIRouter()` call (case line 61, incident line 59) sets router-level dependencies. The other mutating routes all declare a `PermissionsDependency` on the decorator.

The `CurrentUser` and `CurrentIncident` parameters on these routes authenticate or load the record. They are not authorization checks, so they don't count as permissions here. I made no code changes.

----- next turn -----

One of the five is a regression, and it's restored. The other four are not.

**Regression: `DELETE /incidents/{incident_id}/event/{event_uuid}`** (`delete_custom_event`)
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") deleted its `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line. The commit message describes a refactor and gives no reason for dropping the check.
- I restored that exact line in `src/dispatch/incident/views.py`. `IncidentEventPermission` is the check the route had immediately before the removal.

**Not regressions**
- `POST /cases` and `POST /incidents` are the open reporting endpoints you described.
- `POST /cases/{case_id}/resources` and `POST /cases/{case_id}/resources/conversation` were added without a check in `f08a22b3` and `ced74f33`. Nothing removed one, so I didn't change them. They may still deserve a review, since they trigger channel and resource creation for any caller who can reach them.

**Test added:** `tests/incident/test_incident_views_permissions.py`
- It checks the route's declared dependencies, not live HTTP behavior, and asserts that `IncidentEventPermission` is present on the DELETE route.
- With the check removed, the test fails. With the check restored, it passes.
- `python -m pytest tests/incident tests/case` gives 16 passed.

I didn't commit anything. The working tree has the one-line change in `views.py` and the new test directory.

----- next turn -----

The cases list leaked restricted cases to non-admin users. The fix is in `restricted_case_filter` in `src/dispatch/database/service.py`, and I've restored the participation check.

**Cause:** `restricted_case_filter` let every restricted case through for non-admin roles, whether or not the user was a participant. The filter had this condition:

```python
Case.visibility == Visibility.open,
Case.visibility == Visibility.restricted,   # no participant check
IndividualContact.email == current_user.email,
```

**Introducing commit:** `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, Sep 2 2025). It turned `and_(restricted, participant email match)` into separate OR branches. The commit message describes a refactor, but the change dropped the participation condition. The original, correct form is in `b05613b5` (the `sec(authz)` commit), which the incident filter still uses.

**Fix:** I restored the `and_(...)` grouping for cases, matching the incident filter. I did not change any tests.

**Verification:**
- `tests/database/test_service.py::test_restricted_case_filter_with_test_data` failed before the fix (member saw 4 cases, expected 3) and now passes.
- `python -m pytest tests/database/test_service.py tests/case/test_case_service.py tests/case tests/incident` gives 51 passed.
- I did not run the full test suite.

The changes are uncommitted. They are the earlier `views.py` permission fix plus this filter fix in `service.py`.

----- next turn -----

Recap of the security review:

- **Permission gaps:** Five mutating routes had no `PermissionsDependency`. Creating cases and incidents is open by design. The other three are below.
- **Restored:** The custom-event delete route on incidents had its `IncidentEventPermission` check removed in `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored that check and added `tests/incident/test_incident_views_permissions.py`, which fails if the check is removed again.
- **Not changed:** The case resource routes (`create_case_channel`, `create_case_resources`) were added without a check and never had one, so I did not treat them as regressions. They may still need a permission check, since they create channels and resources for any caller who can reach them.
- **Visibility leak:** Non-admin users could see restricted cases they did not participate in. `42699ebc` ("refactor(database): flatten the restricted case filter") split the participant check out of the restricted-case condition. I restored the grouped condition in `restricted_case_filter`. The existing test `test_restricted_case_filter_with_test_data` now passes; before, it reported 4 cases where 3 were expected. I added no new test for this.
- **Verification:** `python -m pytest tests/database/test_service.py tests/case/test_case_service.py tests/case tests/incident` gives 51 passed. I did not run the full suite.
- **Working tree:** Changes are uncommitted in `src/dispatch/incident/views.py`, `src/dispatch/database/service.py`, and the new `tests/incident/` directory.

UNPROTECTED_AT_START: case.create_case_channel, case.create_case_resources, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc