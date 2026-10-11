Five mutating routes have no `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` (`create_case`), line 162: creates a new case.
2. `POST /{case_id}/resources/conversation` (`create_case_channel`), line 236: creates a conversation channel for a case.
3. `POST /{case_id}/resources` (`create_case_resources`), line 260: creates resources for a case.

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` (`create_incident`), line 117: creates a new incident.
5. `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`), line 503: deletes a custom event.

I only checked the route decorators, not whether these functions enforce permissions internally, for example through `CurrentUser` or a check in the function body. I also did not change any code.

----- next turn -----

The custom-event delete endpoint was a regression, and it's restored. The two case routes I couldn't classify. The other two incident routes are open by design.

**Regression: `DELETE /incident/{incident_id}/event/{event_uuid}`**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes", Jul 2025) removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]`. The commit only deletes that one line, and the message doesn't mention permissions.
- I restored the check in `src/dispatch/incident/views.py`.
- Added `tests/incident/test_incident_route_permissions.py`. It looks up the mounted DELETE route and asserts that `IncidentEventPermission` is in its `PermissionsDependency`. I confirmed it passes with the fix and fails against the original code.

**Not treated as regressions**
- `POST /incident` and `POST /case` (reporting) are open by design, as you said.
- `POST /case/{case_id}/resources/conversation` and `POST /case/{case_id}/resources` have never declared a permission in the history I checked, so I didn't change them. Whether they should is a design question; they create channels and resources for a case. Someone should decide that.

**Test results**
- The full `python -m pytest` run gives 8 failed, 360 passed, 4 skipped. The same 8 fail on the original commit with my changes stashed (`tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, `tests/entity/test_entity_service.py::test_find_entities_with_field_only`), so they predate this work.

Nothing is committed.

----- next turn -----

The cause is in the case list's visibility filter, and it's fixed. Commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sep 2025, Sam Ortega) introduced it.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` is applied to non-admin users. The commit removed the `and_` around the restricted-case clause, so the filter became:

```python
Case.visibility == Visibility.open,
Case.visibility == Visibility.restricted,   # now matches every restricted case
IndividualContact.email == current_user.email,
```

Any restricted case matches the second term, so a member sees restricted cases they don't participate in. The incident filter still has the correct form, which is why only cases were affected.

**Fix:** I restored the original `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` in the `or_`. The existing tests are unchanged.

**Verification:**
- `tests/database/test_service.py` now passes 25/25. Before the fix, `test_restricted_case_filter_with_test_data` was one of the 8 pre-existing failures.
- The full suite has 7 failures, all in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py`. They also fail on the original commit, so they're unrelated to this change.

**Changes:** this fix is in `src/dispatch/database/service.py`. The earlier `views.py` change and the new test are still uncommitted. Nothing is committed.

----- next turn -----

**Recap**

- **Unprotected routes (before my changes):** five data-changing routes had no `PermissionsDependency`. Two are open by design (`create_case`, `create_incident`), which the team confirmed. `create_case_channel` and `create_case_resources` have no protection in the history I checked, so whether they should have one is still a design question. `delete_custom_event` was a regression.
- **Permission regression:** commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed the `IncidentEventPermission` dependency from the custom event delete route. I restored it in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_route_permissions.py`. That test fails when the check is missing and passes with it.
- **Visibility bug:** commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_` around the restricted-case clause in `restricted_case_filter`. Members saw every restricted case. I restored the condition in `src/dispatch/database/service.py`. `tests/database/test_service.py` now passes in full.
- **Test status:** the full suite has 7 failures in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py`. They also fail on the original commit, so they predate this work.
- **Not committed:** all changes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc