Five data-changing routes declare no `PermissionsDependency` in their route definition. I read every POST, PUT, PATCH and DELETE decorator in both files, so this list is complete for those two files.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST "/{case_id}/resources/conversation"` → `create_case_channel` (line 236)
3. `POST "/{case_id}/resources"` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE "/{incident_id}/event/{event_uuid}"` → `delete_custom_event` (line 503)

Every other mutating route in both files declares a `PermissionsDependency`. I didn't check whether the router is mounted with a router-level dependency, such as authentication, that these routes would inherit. The list covers only what the route definitions declare.

I didn't change any code.

----- next turn -----

Yes. One of the three was a regression: the incident `DELETE /{incident_id}/event/{event_uuid}` route (`delete_custom_event`).

- **Cause:** commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from that route. Its message calls it a refactor, but it was a one-line deletion that dropped the authorization check. The sibling routes (create, update and export event) still have the check.
- **Fix:** I put that same dependency back in `src/dispatch/incident/views.py`.
- **Test:** the new `tests/incident/test_incident_views.py` looks up the DELETE route and asserts that `IncidentEventPermission` is among its permission classes.
  - It passes with the fix.
  - It fails when I temporarily stashed the fix.
- **Not committed:** the changes are in the working tree only.

I found no matching removal for the two case routes, `create_case_channel` and `create_case_resources`. Their original commits (`ced74f33` and `f08a22b3`) are the only ones that touched those routes' paths, and I didn't diff either one to see whether it ever had a check. Treat them as unconfirmed, not cleared. Neither takes a permission dependency today, so whether they should is a design question for you.

----- next turn -----

The cases list was showing restricted cases to people who aren't participants. The cause is in `restricted_case_filter` in `src/dispatch/database/service.py`, and I've fixed it.

**Cause:** the filter is applied to every non-admin user, and it flattened its `or_` condition into three separate options:
- the case is open,
- **or** the case is restricted (no participant check),
- **or** the user is a participant.

The middle option made every restricted case visible to everyone.

**Commit that introduced it:** `42699ebc`, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2 Sep 2025). It replaced `and_(restricted, participant email == user)` with the two bare conditions. This is the same pattern as the earlier regression: a "refactor" commit that quietly removed an access check.

**Fix:** I restored the `and_` so a restricted case shows only if the user is a participant. The incident filter next to it never had this problem.

**Tests:** I changed no existing tests. The `tests/database`, `tests/case` and `tests/incident` suites pass (41 tests), but none of them exercises this filter. I didn't add a regression test, since you only asked for the fix. I can add one if you want.

The changes are uncommitted and sit alongside the earlier permission fix in the working tree.

----- next turn -----

**Recap**

- **Audit:** five data-changing routes in the case and incident APIs had no `PermissionsDependency`. Two of them (`create_case` and `create_incident`) are open on purpose, because anyone may report a case or an incident.
- **Permission regression:** the incident `delete_custom_event` route lost its `IncidentEventPermission` check in commit `28c21e1e`, which was labelled a refactor. I restored the check. I also added `tests/incident/test_incident_views.py`, which fails if the check goes missing again.
- **Unconfirmed:** `create_case_channel` and `create_case_resources` have no permission check today, and I found no commit that removed one. I didn't diff their original commits (`ced74f33` and `f08a22b3`), so I can't say they never had one.
- **Visibility bug:** commit `42699ebc`, also labelled a refactor, flattened the `or_` in `restricted_case_filter`. That let non-admin users see every restricted case in the list. I restored the `and_` so a restricted case shows only to its participants. The existing tests pass (41 in `tests/database`, `tests/case` and `tests/incident`), but none of them covers this filter, and I added no test for it.
- **State:** all changes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc