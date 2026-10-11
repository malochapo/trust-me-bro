Four routes in the two files change data without a `PermissionsDependency` in their route definition:

1. `src/dispatch/incident/views.py:117`, `POST ""`, `create_incident`
2. `src/dispatch/incident/views.py:503`, `DELETE /{incident_id}/event/{event_uuid}`, `delete_custom_event`
3. `src/dispatch/case/views.py:162`, `POST ""`, `create_case`
4. `src/dispatch/case/views.py:236`, `POST /{case_id}/resources/conversation`, `create_case_channel`

The case file also has `POST /{case_id}/resources` at line 260 (`create_case_resources`), which has no permissions declaration either. That makes five routes in total, not four.

I checked only the route decorators in these two files. Both routers are created with a bare `APIRouter()`, so no router-level dependencies apply. I did not check how `api_router` is mounted in `main.py` or elsewhere. No code was changed.

----- next turn -----

One of the open routes was a regression, and I've restored its check and added a test for it. I haven't committed anything.

**Regression: `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`)**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from this route. The commit message describes a refactor, and the diff is a one-line deletion.
- I restored that line in `src/dispatch/incident/views.py`.
- I added `tests/incident/test_incident_event_views.py`. It looks up the DELETE route on the incident router and asserts that `IncidentEventPermission` is among its permission dependencies. It fails on the unfixed code and passes with the fix.
- `python -m pytest tests/incident tests/case` gives 16 passed.

**Not regressions**
- `POST /incident` (`create_incident`) and `POST /case` (`create_case`): open on purpose, as you said.
- `POST /case/{case_id}/resources/conversation` (`create_case_channel`): added in `ced74f33` with no permission from the start.
- `POST /case/{case_id}/resources` (`create_case_resources`): added in `f08a22b3` with no permission from the start.

I also need to correct my first answer. I named five routes but listed only four, and the list above is the full set of five. The two case resource routes never had a check, so they're gaps to decide on, not regressions.

----- next turn -----

The cause is in `restricted_case_filter` (`src/dispatch/database/service.py`). Its `or_` had `Case.visibility == Visibility.restricted` as a bare term, so every restricted case matched for non-admin users, whether or not they were a participant. I've fixed it by restoring the `and_` wrapper, so a restricted case is visible only to a participant with the user's email. The incident filter already works this way.

**Introducing commit:** `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). It removed the `and_(...)` wrapper as part of the refactor and changed nothing else in that function.

**Verification:**
- With the fix, `python -m pytest tests/database tests/case tests/case_cost` gives 59 passed.
- Without the fix, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` fails: four cases come back where it expects fewer. So the existing test catches the bug, and I didn't change any tests.

I haven't committed anything. The working tree also still has the earlier `delete_custom_event` fix and its new test.

----- next turn -----

Recap of the security review, covering the three findings:

**1. Mutating routes without a `PermissionsDependency`.** Five handlers in `case/views.py` and `incident/views.py` changed data with no permission declared. Two are open on purpose: `create_incident` and `create_case`. The other three are `case.create_case_channel` and `case.create_case_resources`, which have never had a check, and `incident.delete_custom_event`, which had one until it was removed. The first answer named four routes in its list but five in its text. The five above are the full set.

**2. Regression in `delete_custom_event`.** Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `IncidentEventPermission` from `DELETE /incident/{incident_id}/event/{event_uuid}`. I restored the check in `src/dispatch/incident/views.py`. I added `tests/incident/test_incident_event_views.py`, which asserts the dependency is on the route. It fails without the fix and passes with it.

**3. Members seeing restricted cases they're not part of.** `restricted_case_filter` in `src/dispatch/database/service.py` let every restricted case through for non-admin users. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_` that ties restricted visibility to participation. I restored it. `tests/database`, `tests/case` and `tests/case_cost` pass with 59 tests, and the existing `test_restricted_case_filter_with_test_data` fails on the unfixed code. I didn't change any tests.

Both fixes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc