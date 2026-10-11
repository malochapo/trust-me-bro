Five data-changing routes have no `PermissionsDependency` in their route definition. I checked this with a script over every `@router.post/put/patch/delete` decorator (27 in total: 13 in the case API, 14 in the incident API). I didn't change any code.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` (`create_case`, line 162) creates a new case.
2. `POST /{case_id}/resources/conversation` (`create_case_channel`, line 236) creates a conversation channel for an existing case.
3. `POST /{case_id}/resources` (`create_case_resources`, line 260) creates resources for an existing case.

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` (`create_incident`, line 117) creates a new incident.
5. `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`, line 503) deletes a custom event.

The check looked for `PermissionsDependency` in each decorator block, up to the `def` line. It would not catch a route that enforces permissions some other way, such as an in-function check or a router-level dependency. I didn't look for either. Tell me if you want me to.

----- next turn -----

Yes, one of them is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`). I restored its check and added a test. The new test passes with the fix and fails when I stash the fix. I did not run the rest of the suite.

**The regression**
- Commit `28c21e1e`, "refactor(incident): tidy custom event routes", removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from this route. The commit message calls it a tidy-up, but the diff changes who can call the endpoint.
- Every sibling event route in the incident views (lines 420, 445, 477 and 598) still has that same dependency. Without it, any authenticated user could delete an incident's timeline events.

**The fix**
- I put the same `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` back on the route in `src/dispatch/incident/views.py`.

**The test**
- `tests/incident/test_incident_event_views.py` checks that the DELETE route includes `IncidentEventPermission`. It reads the router's route metadata instead of making a request, so it doesn't depend on test users or roles.

**The two case routes I didn't change**
- `create_case_channel` and `create_case_resources` have no check in their history that I could find. They were added unprotected in `ced74f33` and `f08a22b3`. I found no evidence that either lost a check, so I treated them as original design and left them alone.
- They create resources on an existing case, so they may still deserve a permission. That would be a new decision, not a restoration.

Nothing is committed.

----- next turn -----

Fixed. Commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2 Sep 2025) introduced the bug.

**Cause.** `restricted_case_filter` in `src/dispatch/database/service.py` decides what non-admin users see in the cases list. The original rule was "open, or restricted and the user is a participant". The commit removed the `and_(...)`, so the rule became three separate alternatives:

- `Case.visibility == open`
- `Case.visibility == restricted`
- `IndividualContact.email == current_user.email`

The second alternative matches every restricted case, whoever the user is. That is why the security team member sees restricted cases they don't take part in. Admin, owner and manager roles skip this filter, so they were not affected. `restricted_incident_filter` still has the `and_` and was fine.

**Fix.** I put the `and_(restricted, email == current_user.email)` grouping back. I didn't touch any tests. `tests/case` and `tests/database` pass (40 passed), but they don't exercise this filter, so that result doesn't confirm the fix.

I haven't added a regression test for it, since you asked only for the fix. I can add one that checks a non-participant doesn't get a restricted case. Nothing is committed.

----- next turn -----

## Recap

**1. Audit of unprotected data-changing routes.** A scan of every POST, PUT, PATCH and DELETE route in the case and incident APIs found five without a `PermissionsDependency`. Two are intentionally open (anyone may report a case or an incident): `create_case` and `create_incident`. The other three are `create_case_channel`, `create_case_resources` and `delete_custom_event`.

**2. Regression: `incident.delete_custom_event`.**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") dropped its `IncidentEventPermission` check.
- Every sibling event route still has the check.
- I restored it in `src/dispatch/incident/views.py`.
- I added `tests/incident/test_incident_event_views.py`. It passes with the fix and fails without it.
- The two case resource routes had no check anywhere in their history, so I left them unchanged. They may still deserve a permission, but that would be a new decision.

**3. Visibility bug.**
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_` in `restricted_case_filter`. The filter then matched every restricted case, regardless of participation.
- I restored the `and_` in `src/dispatch/database/service.py`.
- `tests/case` and `tests/database` pass (40 passed), but they don't exercise this filter.
- I haven't added a regression test for it.

Nothing is committed. I did not run the full test suite, only the new test and the case and database tests.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc