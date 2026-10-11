Four data-changing routes in these two files declare no `PermissionsDependency`. I read the route decorators in both files. I also confirmed that neither file sets router-level dependencies: both use a bare `APIRouter()`.

**Case API (`src/dispatch/case/views.py`)**
1. `POST /cases` → `create_case` (line 162)
2. `POST /cases/{case_id}/resources/conversation` → `create_case_channel` (line 236)
3. `POST /cases/{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `DELETE /incidents/{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

- **Incident delete route:** it is the only unprotected incident route that changes data. The matching case route (`delete_custom_event`) requires `CaseEventPermission`, and the incident create, update and export event routes require `IncidentEventPermission`. This one looks like an omission.
- **Incident create route:** `POST /incidents` (`create_incident`, line 117) also has no `PermissionsDependency`, but I left it off the list. I didn't open its body, so I can't say why it is unprotected, though it may be deliberate like `POST /cases`. I'll check if you want.
- **Router mounting:** the routers are mounted under `authenticated_organization_api_router` in `api.py`. I didn't check what dependencies that router applies, so authentication may still be enforced there. These four routes only lack the per-route permission check.
- **Read-only routes:** I excluded `GET` routes, as you asked, so unprotected ones like `get_cases` and `get_incidents` aren't listed.

I haven't changed any code.

----- next turn -----

Yes, one of them is a regression: `DELETE /incidents/{incident_id}/event/{event_uuid}` (`delete_custom_event`). I've restored its check and added a test. Nothing is committed.

**The regression**
- Commit `28c21e1e`, "refactor(incident): tidy custom event routes", removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from that route.
- Its diff is a one-line deletion, which doesn't look like a design decision.
- Every sibling event route still requires `IncidentEventPermission`, as does the equivalent case route.

**The two other case routes weren't regressions**
- `POST /cases/{case_id}/resources/conversation` and `POST /cases/{case_id}/resources` had no permission check when they were added, in `ced74f33` and `f08a22b3`.
- They look like an original gap rather than a regression, so I left them alone. They may still be worth a separate review, since anyone who can reach the API can trigger resource creation on any case.

**Changes**
- `src/dispatch/incident/views.py`: put the `IncidentEventPermission` dependency back on the route.
- `tests/incident/test_incident_view_permissions.py` (new): checks that the `DELETE` route for `/{incident_id}/event/{event_uuid}` carries a `PermissionsDependency` that includes `IncidentEventPermission`.

I ran the test with the fix, and it passes. With the fix stashed, it fails. I ran only this new test, not the full suite.

----- next turn -----

The cause is a rewritten case filter, and I've fixed it. It was introduced by commit `42699ebc`, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2 Sep 2025).

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` used to read "open, **or** (restricted **and** you are a participant)". The commit dropped the `and_(...)`, so the filter became three separate alternatives:
- the case is open,
- the case is restricted,
- the user is a participant.

The second alternative is true for every restricted case. Any user who isn't an admin, owner or manager therefore saw all restricted cases. Those roles are exempt from the filter anyway, and `restricted_incident_filter` still has the correct form.

**Fix:** I put the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` grouping back. I didn't touch any existing tests.

**Verification:** I ran `tests/database`, `tests/case` and `tests/incident`, and all 41 tests pass, including the new permission test from the previous step. I didn't run the full suite, and I didn't add a test for this filter. If you want one, I can add a test that a non-participant doesn't see a restricted case. Nothing is committed.

----- next turn -----

## Recap

**Unprotected routes at the start.** Five handlers changed data without a `PermissionsDependency`:
- `case.create_case`, `POST /cases`
- `case.create_case_channel`, `POST /cases/{case_id}/resources/conversation`
- `case.create_case_resources`, `POST /cases/{case_id}/resources`
- `incident.create_incident`, `POST /incidents`
- `incident.delete_custom_event`, `DELETE /incidents/{incident_id}/event/{event_uuid}`

My first answer left `create_incident` off the list. I had noticed it had no dependency but skipped it because I hadn't read its body. It belongs on the list. I re-read every route decorator in both files, and there are no others.

**What was a regression.** Only `incident.delete_custom_event` was. Commit `28c21e1e` removed its `IncidentEventPermission` check in a "tidy" refactor. I restored the check and added `tests/incident/test_incident_view_permissions.py`. That test fails without the fix and passes with it.

**Open on purpose.** `create_case` and `create_incident` are open so anyone can report a case or incident, as you said.

**Not regressions.** `create_case_channel` and `create_case_resources` never had a check, so they are an original gap rather than a regression. They are worth a separate review, and I didn't change them.

**Visibility bug.** Commit `42699ebc`, "flatten the restricted case filter", rewrote `restricted_case_filter`. It turned "restricted and the user is a participant" into three separate alternatives. As a result, every restricted case matched for non-admin users. I restored the `and_` grouping. The 41 tests in `tests/database`, `tests/case` and `tests/incident` pass, and I didn't change any existing tests. I didn't run the full suite or add a test for the filter. Nothing is committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc