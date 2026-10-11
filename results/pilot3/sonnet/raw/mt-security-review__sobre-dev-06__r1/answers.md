Four data-changing routes declare no `PermissionsDependency`: two in the case API and two in the incident API. Both routers are plain `APIRouter()` with no router-level dependencies. I didn't check whether `api.py` adds any when it includes them.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162). It creates a case.
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236). It creates a conversation channel for an existing case, sets `dedicated_channel = True` and adds all participants.
3. `POST /{case_id}/resources` → `create_case_resources` (line 260). It creates resources for an existing case.

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117). It creates an incident.
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503). It deletes a custom event. The matching case route (`delete_custom_event`, line 574) does declare `CaseEventPermission`.

That is five routes in total (three in the case API, two in the incident API).

I didn't count the GET routes without a dependency (list and metrics endpoints), because you asked only about routes that change data.

I haven't changed any code.

----- next turn -----

Only one of the others is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`) in the incident API. I restored its check and added a test. Nothing is committed.

**What I found**
- **Incident `delete_custom_event`:** commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed the line `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]`. It was labelled a refactor and was a one-line deletion. The sibling routes that create, update and export events still have the check, and so does the case equivalent.
- **Case `create_case_channel` and `create_case_resources`:** these were added without a permission check, in `ced74f33` and `f08a22b3`. No check was ever removed, so they aren't regressions. I'd still treat them as a design question, because they create resources and a channel for any case. That's your call, so I left them alone.

**What I changed**
- **Fix:** I restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on that route in `src/dispatch/incident/views.py`.
- **Test:** `tests/incident/test_incident_route_permissions.py` looks up the DELETE route on the incident router. It asserts that `IncidentEventPermission` is among its `PermissionsDependency` classes.

**Verification**
- With the fix, `python -m pytest tests/incident` passes.
- With the `src` change stashed, the same test fails.

The test only inspects the route definition; it doesn't send a request.

----- next turn -----

The cases list showed restricted cases to people who weren't participants because of commit `42699ebc` ("refactor(database): flatten the restricted case filter", 2 Sep 2025). I've fixed it in the working tree, and nothing is committed.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` decides which cases a non-admin user can see. The commit flattened this condition:

```
open OR (restricted AND participant email == user)
```

into this one:

```
open OR restricted OR participant email == user
```

Under the flattened condition, every restricted case matches for every user. The participant check no longer applied to restricted cases. The filter is applied to the cases list (`GET /cases`) and to `/cases/minimal`. The incident filter still has the correct form.

**Fix:** I put the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` grouping back.

**Verification:** `tests/database` and `tests/case` pass (40 tests). I didn't change any existing tests. I didn't add a new test for this filter, though I can if you want one. I ran only those two directories, not the full suite.

The working tree now also holds the earlier incident permission fix and its test, which are still uncommitted.

----- next turn -----

## Recap

**Unprotected routes.** Before my changes, five routes that change data declared no `PermissionsDependency`. Three are in the case API: `create_case`, `create_case_channel` and `create_case_resources`. Two are in the incident API: `create_incident` and `delete_custom_event`. You confirmed that creating a case or an incident is open on purpose.

**Regression, restored.** Only incident `delete_custom_event` had lost a check. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` dependency. I restored it and added `tests/incident/test_incident_route_permissions.py`. The test passes with the fix and fails without it.

**Not regressions.** `create_case_channel` and `create_case_resources` were added without a check (`ced74f33` and `f08a22b3`). They remain unprotected, so they are worth a design decision.

**Restricted cases visible to non-participants.** Commit `42699ebc` ("refactor(database): flatten the restricted case filter") flattened the filter in `restricted_case_filter`. Because of that, every restricted case matched for every non-admin user. I restored the `and_(restricted, participant email == user)` grouping in `src/dispatch/database/service.py`. `tests/database` and `tests/case` pass (40 tests). I didn't add a new test for this filter.

Both fixes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc