Five endpoints change data without a `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST /cases`: `create_case` (line 162)
2. `POST /cases/{case_id}/resources/conversation`: `create_case_channel` (line 236)
3. `POST /cases/{case_id}/resources`: `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST /incidents`: `create_incident` (line 117)
5. `DELETE /incidents/{incident_id}/event/{event_uuid}`: `delete_custom_event` (line 503)

I only checked the route decorators in each file. Both routers are created with a bare `APIRouter()`, so no router-level dependencies apply. The case router is mounted under `authenticated_organization_api_router` in `src/dispatch/api.py:191`, and I did not check whether that mount adds a permission check. No code was changed.

----- next turn -----

Yes, one of them is a regression. The incident `DELETE /incidents/{incident_id}/event/{event_uuid}` route (`delete_custom_event`) lost its `IncidentEventPermission` check in commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, Jul 14 2025). That commit removed only the `dependencies=` line, and every other custom-event route in the file still has the check.

**Fix**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on `delete_custom_event`.
- `tests/incident/test_incident_event_route_permissions.py` (new): finds the DELETE route on the incident router and asserts `IncidentEventPermission` is among its permission classes. I ran it against the unfixed code and it failed with `IncidentEventPermission in []`, then passed after the fix.

**Results**
- `python -m pytest tests/case tests/incident`: 16 passed.

**Not changed**
- `POST /cases/{case_id}/resources/conversation` (`create_case_channel`) and `POST /cases/{case_id}/resources` (`create_case_resources`) have never had a permission check. Commits `ced74f33` and `f08a22b3` added them without one, so I did not treat them as regressions. Whether they should be gated is a decision for you. The incident equivalent, `POST /incidents/{incident_id}/resources`, uses `IncidentViewPermission`.
- `POST /cases` and `POST /incidents` are the open-by-design reporting routes, so I left them alone.

----- next turn -----

The cases list was showing restricted cases to people who aren't participants. The cause is in `restricted_case_filter` in `src/dispatch/database/service.py`. The commit that introduced it is `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, Sep 2 2025).

**Cause**
That commit turned `and_(restricted, participant email matches)` into two separate OR terms:
```python
Case.visibility == Visibility.restricted,
IndividualContact.email == current_user.email,
```
A restricted case now matches on its own, so any non-admin sees every restricted case. The commit message says refactor, but it changed behaviour. The incident version of the filter still has the correct grouping.

**Fix**
I restored the `and_` grouping in `src/dispatch/database/service.py`. Admin, owner and manager roles are unchanged.

**Verification**
- `python -m pytest tests/database tests/case`: 40 passed with the fix.
- With the file reverted to HEAD, `test_restricted_case_filter_with_test_data` fails, so the existing test already catches this bug. I did not change any tests.

**Still uncommitted from earlier**
The incident `delete_custom_event` permission fix and the new test in `tests/incident/` are still in the working tree. This change is also uncommitted. I haven't committed anything.

----- next turn -----

Recap of the security review:

- **Unprotected endpoints (data-changing, no `PermissionsDependency`):** five. `POST /cases`, `POST /cases/{case_id}/resources/conversation` and `POST /cases/{case_id}/resources` in the case API; `POST /incidents` and `DELETE /incidents/{incident_id}/event/{event_uuid}` in the incident API. `POST /cases` and `POST /incidents` are open by design, so they are not findings.
- **Regression restored:** the incident `DELETE` custom-event route. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_event_route_permissions.py`, which fails if the check goes missing again. It failed before the fix and passes after.
- **Visibility bug:** `restricted_case_filter` in `src/dispatch/database/service.py` showed restricted cases to non-participants. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") split a grouped condition into two OR terms. I restored the grouping. The existing test `test_restricted_case_filter_with_test_data` fails without the fix and passes with it, and I changed no tests.
- **Not changed:** the two case resource routes (`create_case_channel`, `create_case_resources`) have never had a check, so I did not classify them as regressions. Whether they should be gated is your decision.
- **Uncommitted:** both fixes and the new test are in the working tree. Nothing is committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc