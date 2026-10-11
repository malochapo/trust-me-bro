Four data-changing routes declare no `PermissionsDependency` in their route definition. I checked this by reading the decorators in both files. Every other POST, PUT, PATCH and DELETE route declares one.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""`, `create_case`, line 162.
2. `POST /{case_id}/resources/conversation`, `create_case_channel`, line 236.
3. `POST /{case_id}/resources`, `create_case_resources`, line 260.

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""`, `create_incident`, line 117.
5. `DELETE /{incident_id}/event/{event_uuid}`, `delete_custom_event`, line 503.

That is five routes, not four: three in the case API and two in the incident API.

This only checks the route decorators. A route could still be protected some other way, for example by a router-level dependency or by an auth check in the function body. I didn't check either.

The incident `delete_custom_event` stands out. The matching create, update and export event routes all use `IncidentEventPermission`, and the case API's `delete_custom_event` uses `CaseEventPermission`.

I haven't changed any code.

----- next turn -----

Yes, one of them is a regression: the incident `DELETE /{incident_id}/event/{event_uuid}` route (`delete_custom_event`). I've restored its check and added a test. Nothing is committed.

**Which commit removed it:** `28c21e1e`, "refactor(incident): tidy custom event routes". It deleted `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from that route and changed nothing else. The sibling create, update and export routes still have the check.

**Not regressions:** `create_case_channel` and `create_case_resources` were added without a `PermissionsDependency`, in `ced74f33` and `f08a22b3`, so they were never protected. That is probably a gap, but it isn't a regression. If you want them locked down, say which permission they should use. `CaseEditPermission` would match the other case mutation routes.

**Changes:**
- `src/dispatch/incident/views.py`: put the `IncidentEventPermission` dependency back on `delete_custom_event`.
- `tests/incident/test_incident_event_permissions.py` (new): checks that the four incident timeline-event routes each declare `IncidentEventPermission`. Those routes are POST and PATCH on `/{incident_id}/event`, POST on `/{incident_id}/exportTimeline`, and the DELETE above.

**Verification:** the test passes with the fix. With `views.py` stashed back to the broken version, it fails. I only ran the new test, not the full suite.

----- next turn -----

The cause is commit **`42699ebc`**, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2025-09-02). I've fixed it in the working tree, and nothing is committed.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` is meant to return a case if it is open, or if it is restricted and the user is a participant. The commit removed the `and_(...)` around the restricted clause. The filter became `open OR restricted OR email == user`, so every restricted case matched the middle clause for every non-admin user, whether or not they take part. Admins, owners and managers skip this filter, so only other roles saw the leak.

**Fix:** I put the `and_(Case.visibility == restricted, IndividualContact.email == current_user.email)` back. This matches `restricted_incident_filter`, which still has it.

**Verification:** `tests/database/test_service.py` passes (25 tests), and I didn't change any tests. I haven't run the whole suite.

----- next turn -----

**Recap**

- **Unprotected routes:** Five routes changed data without a `PermissionsDependency`. Two of them, `create_case` and `create_incident`, are open on purpose, because anyone may report a case or an incident. `create_case_channel` and `create_case_resources` never had a check. That is probably a gap, but it isn't a regression, and I left both alone. They are still open, and you'd need to choose a permission for them. `CaseEditPermission` would match the other case mutation routes.
- **Regression restored:** The incident `delete_custom_event` route lost its `IncidentEventPermission` check in `28c21e1e`. I restored it in `src/dispatch/incident/views.py`. I added `tests/incident/test_incident_event_permissions.py`, which fails if any of the four incident timeline-event routes loses that check. It passes with the fix and fails without it.
- **Visibility bug:** `42699ebc` removed the `and_(...)` around the restricted clause in `restricted_case_filter` (`src/dispatch/database/service.py`). The filter then matched every restricted case for non-admin users. I restored the `and_`. `tests/database/test_service.py` passes (25 tests), and I didn't change any existing test.
- **Not done:** Nothing is committed. I ran only the new test and `tests/database/test_service.py`, not the full suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc