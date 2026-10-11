Five mutating routes declare no `PermissionsDependency` in their route definition.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162, "Creates a new case.")
2. `POST "/{case_id}/resources/conversation"` → `create_case_channel` (line 236)
3. `POST "/{case_id}/resources"` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117, "Creates a new incident.")
5. `DELETE "/{incident_id}/event/{event_uuid}"` → `delete_custom_event` (line 503)

I checked only the route decorators for a `dependencies=[Depends(PermissionsDependency(...))]` argument. A route could still be protected some other way, for example by a router-level dependency, an include-time dependency, or a check inside the function body. I didn't check any of those.

The incident `delete_custom_event` stands out. Its sibling event routes (create, update, export) all require `IncidentEventPermission`, and the case equivalent `delete_custom_event` requires `CaseEventPermission`.

I haven't changed any code.

----- next turn -----

Yes, one of them is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event` in `src/dispatch/incident/views.py`). I restored its check and added a test. Nothing is committed.

**The regression**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from this route. That commit message describes a tidy-up, but it dropped an access check.
- Its sibling routes (create, update, export) still require that permission. The case equivalent of the delete route does too.
- Without the check, any authenticated user could delete another incident's timeline events.

**Not regressions**
- `create_case_channel` and `create_case_resources` (case API) were added without a permission dependency. I read the history for the channel route (`ced74f33`); I couldn't tell from the diff for the resources route (`f08a22b3`). I found no removal for either, so they look like gaps from the start rather than regressions.
- They still allow any authenticated user to trigger resource or channel creation for any case. That may be worth a separate decision.

**Changes**
- `src/dispatch/incident/views.py`: I restored the original dependency line on the delete route.
- `tests/incident/test_incident_event_permissions.py` (new):
  - It inspects the incident router's route definitions and asserts that every custom-event route requires `IncidentEventPermission`. Those are create, update, export timeline and delete.
  - It also asserts that at least four such routes exist, so a path rename can't make it pass without checking anything.

**Verification**
- With the fix, the test passes.
- With the fix stashed, the test fails.
- I couldn't run `ruff` because it isn't installed here, so lint and formatting are unchecked.

----- next turn -----

The restricted-case filter in `src/dispatch/database/service.py` (`restricted_case_filter`) had been loosened to let every restricted case through. I've restored the original condition. The change is uncommitted.

**Cause:** commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02) flattened a nested condition. The original was:

```
open OR (restricted AND the user is a participant)
```

After the refactor it became:

```
open OR restricted OR the user is a participant
```

That made every restricted case visible to every non-admin, non-manager user, whether or not they took part in it. The incident filter, `restricted_incident_filter`, still has the correct form.

**Fix:** I put the `and_(restricted, participant email)` grouping back, which matches the incident filter. I didn't touch any tests.

**Verification:** `tests/database` and `tests/case` pass (40 tests). I didn't add a regression test for this and didn't check whether one already exists. I can add one if you want.

----- next turn -----

**Recap for the review report**

- **Unprotected mutating routes at the start:** I found five by reading route decorators. Two are open on purpose, because anyone may report a case or an incident. The other three are `create_case_channel` and `create_case_resources` in the case API, and `delete_custom_event` in the incident API. Other protection, such as a router-level dependency or a check inside a function body, wasn't checked.
- **Incident regression, fixed:** commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `IncidentEventPermission` from `DELETE /{incident_id}/event/{event_uuid}`. I restored it in `src/dispatch/incident/views.py`. I added `tests/incident/test_incident_event_permissions.py`, which passes with the fix and fails without it.
- **Case gaps, not fixed:** `create_case_channel` and `create_case_resources` look like gaps from the start rather than regressions. I found no commit that removed a check from either. Any authenticated user can still trigger them for any case. That needs a separate decision.
- **Visibility bug, fixed:** commit `42699ebc` ("refactor(database): flatten the restricted case filter") changed the case filter from `open OR (restricted AND participant)` to `open OR restricted OR participant`. That let every non-admin, non-manager user see all restricted cases. I restored the original grouping in `restricted_case_filter` in `src/dispatch/database/service.py`. The existing `tests/database` and `tests/case` tests pass (40). I didn't add a regression test for this one.
- **Not done:** nothing is committed, and `ruff` wasn't available, so lint and formatting are unchecked.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289