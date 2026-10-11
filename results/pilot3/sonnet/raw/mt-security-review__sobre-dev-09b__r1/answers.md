Five data-changing routes have no `PermissionsDependency` in their route definition.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST "/{case_id}/resources/conversation"` → `create_case_channel` (line 236)
3. `POST "/{case_id}/resources"` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE "/{incident_id}/event/{event_uuid}"` → `delete_custom_event` (line 503)

The other POST, PUT, PATCH and DELETE routes in both files declare a `PermissionsDependency`. I only checked the route decorators in these two files. I did not check whether the router is mounted with its own dependencies elsewhere, for example in `api.py`. Those dependencies would still apply to these five routes, but they would not count as a declaration in the route definition.

Nothing was changed.

----- next turn -----

One of the three was a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event` in `src/dispatch/incident/views.py`). I restored its check and added a test. The new test passes with the fix and fails when the fix is stashed. I only ran that new test file, not the rest of the suite. I haven't committed anything.

**The regression**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from the route. The commit message calls it a refactor, so the removal looks accidental.
- The sibling event routes still have the check: create, update (PATCH) and export.
- I restored the same `IncidentEventPermission` dependency the route had before.

**The others look like design choices**
- `create_case_channel` and `create_case_resources` have never had a check. Both were added without one, in `ced74f33` and `f08a22b3`. They are still unauthenticated state changes on an existing case, so you may want to review them separately.
- The two create routes are open on purpose, as you said.

**The test**
- It is in `tests/incident/test_incident_views_permissions.py`. It finds the DELETE route in the incident router and asserts that `IncidentEventPermission` is among its permission dependencies.
- It inspects the route definition rather than calling the endpoint, so it doesn't depend on database fixtures.

----- next turn -----

The cause is in `restricted_case_filter` in `src/dispatch/database/service.py`. The security team member isn't an admin, owner or manager, so their cases list goes through that filter. It had a flat `or_`, so any case marked `restricted` matched on visibility alone. Participation was never checked for restricted cases. The `IndividualContact.email == current_user.email` term was also loose, so a case matched whenever the user was a participant, whatever its visibility.

**Commit:** `42699ebc`, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2025-09-02). It replaced this:

```python
and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)
```

with two separate `or_` terms. The `and_` was there since `b05613b5` (#6155), and `restricted_incident_filter` still has it.

**Fix:** I put the `and_` back, so a restricted case is visible only to its participants and open cases stay visible to everyone.

I changed no tests. `tests/database/test_service.py` and `tests/case` pass (40 tests), but they passed before the fix too, so none of them covers this case. I haven't added a test for it. The change is uncommitted.

----- next turn -----

**Recap for the review report**

1. **Unprotected data-changing routes.** Five POST/PUT/PATCH/DELETE routes in the case and incident APIs had no `PermissionsDependency`. Creating a case, creating an incident, and the two case resource routes (`create_case_channel`, `create_case_resources`) have never had a check. `create_case` and `create_incident` are open on purpose. The two case resource routes have never been protected, and I left them alone, but they may deserve a separate review.

2. **Regression, fixed.** `incident.delete_custom_event` (`DELETE /{incident_id}/event/{event_uuid}`) lost its `IncidentEventPermission` check in `28c21e1e`, a commit labelled a refactor. I restored the check. I added `tests/incident/test_incident_views_permissions.py`, which fails if the check goes missing again. I confirmed it fails with the fix stashed and passes with it applied.

3. **Visibility bug, fixed.** `restricted_case_filter` in `src/dispatch/database/service.py` let non-admin users see restricted cases they didn't take part in. Commit `42699ebc` ("flatten the restricted case filter") split an `and_(restricted, participant email)` into two separate `or_` terms. As a result, any restricted case matched on visibility alone. I restored the `and_`. The existing tests pass, but none of them covers this behaviour, and I didn't add one.

Both fixes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc