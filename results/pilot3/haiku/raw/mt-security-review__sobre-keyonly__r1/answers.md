Five mutating routes have no `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""`: `create_case`, line 162
2. `POST /{case_id}/resources/conversation`: `create_case_channel`, line 236
3. `POST /{case_id}/resources`: `create_case_resources`, line 260

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""`: `create_incident`, line 117
5. `DELETE /{incident_id}/event/{event_uuid}`: `delete_custom_event`, line 503

I checked only the route decorators, as the question asked. If the router or a function body applies authorization some other way, these would still be unguarded at the route level. No code was changed.

----- next turn -----

Yes, one of them is a regression, and it's restored.

**The regression:** the incident `DELETE /{incident_id}/event/{event_uuid}` route (`delete_custom_event`). Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line. That was a refactor, not a design choice. The other custom-event routes in the same file still have the check.

**The fix:** I restored the line in `src/dispatch/incident/views.py`, matching the other custom-event routes.

**The test:** `tests/incident/test_incident_views_permissions.py` inspects the router and asserts that the DELETE route for `/{incident_id}/event/{event_uuid}` declares a `PermissionsDependency` containing `IncidentEventPermission`. I ran it before the fix and it failed with the check missing, then ran it after the fix and it passed. Running it with `python -m pytest` also ran the existing `tests/case/test_case_event_views.py`, and all 5 tests passed.

**The others aren't regressions:**
- The case `POST /{case_id}/resources` (`create_case_resources`) and `POST /{case_id}/resources/conversation` (`create_case_channel`) routes were added without a check in `f08a22b3` and `ced74f33`. They never had one, so there was no check to restore. If they should be guarded, that's a new decision, and I haven't changed them.
- `create_case` and `create_incident` are the intentionally open ones.

----- next turn -----

The cases list was leaking restricted cases to members who aren't participants. The fix is in place and the existing tests pass.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` let every restricted case through, whether or not the user was a participant. The filter's `or_` had `Case.visibility == Visibility.restricted` as a standalone clause, so the participant check never applied to restricted cases. The incident version of this filter wraps that clause in `and_(...)` with the participant email, which is what the case version needs.

**Commit that introduced it:** `42699ebc7`, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2025-09-02). It is labelled a refactor, but it removed the `and_` and changed behaviour.

**Fix:** I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` clause. No test files were changed.

**Verification:**
- With the fix, `tests/database/test_service.py` and `tests/case` pass (40 tests).
- On the pre-fix code, the existing `test_restricted_case_filter_with_test_data` fails with "Member should see 3 cases (2 open + 1 restricted as participant), got 4". So that test already covers this bug.

I did not add a new test, since the existing one already catches it.

----- next turn -----

## Review recap

**Unprotected routes at the start:** Five routes changed data without a `PermissionsDependency`:
- `case.create_case`: open on purpose, anyone may report a case.
- `case.create_case_channel`: never had a check (added without one in `ced74f33`). Left unchanged; guarding it would be a new decision.
- `case.create_case_resources`: never had a check (added without one in `f08a22b3`). Left unchanged, same reason.
- `incident.create_incident`: open on purpose, anyone may report an incident.
- `incident.delete_custom_event`: a regression, restored.

**Restored check:** `incident.delete_custom_event` had its `PermissionsDependency([IncidentEventPermission])` removed by `28c21e1e` ("refactor(incident): tidy custom event routes"). I put the check back and added `tests/incident/test_incident_views_permissions.py`. The test failed before the fix and passes after it.

**Cases list leaking restricted cases:** `restricted_case_filter` in `src/dispatch/database/service.py` let members see every restricted case, not only the ones they participate in. The commit that introduced it was `42699ebc7` ("refactor(database): flatten the restricted case filter"), which dropped the `and_` that tied restricted visibility to participation. I restored the `and_`. The existing `test_restricted_case_filter_with_test_data` failed before the fix (it got 4 cases where it expects 3) and passes after it. I did not change any existing tests.

**Verification:** `tests/database/test_service.py`, `tests/case`, and the new incident permission test all pass under `python -m pytest`. Nothing is committed; the changes are in the working tree (`src/dispatch/incident/views.py`, `src/dispatch/database/service.py`, and the new `tests/incident/` directory).

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc7