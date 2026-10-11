Five data-changing routes have no `PermissionsDependency` in their route definition:

**`src/dispatch/case/views.py`**
1. `POST ""` → `create_case` (line 162)
2. `POST "/{case_id}/resources/conversation"` → `create_case_channel` (line 236)
3. `POST "/{case_id}/resources"` → `create_case_resources` (line 260)

**`src/dispatch/incident/views.py`**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE "/{incident_id}/event/{event_uuid}"` → `delete_custom_event` (line 503)

I checked each decorator block directly for a `dependencies=` argument, and none of these five has one. The other mutating routes in both files declare a permission.

This is a static read of the route definitions only. Access may still be enforced elsewhere, for example by middleware or inside the handler body, and I did not check that. No code was changed.

----- next turn -----

Yes, one of the five is a regression, and I've restored its check.

**Regression: `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`)**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") deleted its `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line. The commit only removed that line, and the route had been gated since `24ea6ddf`/`328359b5`-era changes.
- I restored the line in `src/dispatch/incident/views.py`. It's the only change to the source.

**Not regressions**
- `POST /case/{case_id}/resources/conversation` (`create_case_channel`) and `POST /case/{case_id}/resources` (`create_case_resources`) were added without a permission check in `ced74f33` and `f08a22b3`. They were never gated, so I left them alone. If they should be restricted, that's a separate decision.
- `POST /case` and `POST /incident` are the open-on-purpose reporting routes you mentioned.

**Test**
- Added `tests/incident/test_incident_route_permissions.py`. It looks up the DELETE route on the incident router and asserts that a `PermissionsDependency` including `IncidentEventPermission` is attached.
- With the line removed, the test fails. With it restored, it passes.

**Test runs**
- `python -m pytest tests/incident tests/case`: 16 passed.
- I ran the suites with `python -m pytest`, as you asked. I didn't run the full suite.

I made one mistake during verification: I checked out the old file version from `28c21e1e` into the index. I reset the index entry, confirmed the working copy matches the restored version, and `git diff HEAD` now shows only the one added line.

----- next turn -----

The fix is in place and the related tests pass.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` allowed every restricted case to any non-admin user. The `Case.visibility == Visibility.restricted` condition sat directly in the `or_(...)`, so the participant check (`IndividualContact.email == current_user.email`) applied only to other clauses. The `/case` list (and `/case/minimal`) run through `apply_model_specific_filters`, so both leaked restricted cases.

**Commit that introduced it:** `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, Sep 2 2025). It removed the `and_(...)` wrapper around the restricted-visibility and participant conditions. The commit message describes a refactor, and the diff makes the change look like a no-op, but it changes the logic.

**Fix:** I restored the `and_(...)` wrapper so restricted cases require the user to be a participant. Admin, owner and manager roles still bypass the filter, as before. This is the only change, and no tests were modified.

**Verification:** `python -m pytest tests/database tests/case tests/api` → 40 passed.

I didn't add a regression test for this. You said the existing tests are correct, and I didn't want to add to the suite without asking. If you want one, I can add a test that a non-admin member doesn't see a restricted case they aren't on.

----- next turn -----

## Review recap

**Unprotected data-changing routes (before my changes):** five handlers had no `PermissionsDependency`.
- `case.create_case` (`POST /case`) and `incident.create_incident` (`POST /incident`): you confirmed these are open on purpose, since anyone can report a case or incident.
- `case.create_case_channel` (`POST /case/{case_id}/resources/conversation`) and `case.create_case_resources` (`POST /case/{case_id}/resources`): added without a check in `ced74f33` and `f08a22b3`. I found no sign they were meant to be open, but I haven't confirmed that with you.
- `incident.delete_custom_event` (`DELETE /incident/{incident_id}/event/{event_uuid}`): this one was a regression.

**Regression fixed:** `incident.delete_custom_event` lost its `IncidentEventPermission` check in `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored the check in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_route_permissions.py`. That test fails when the check is missing and passes with it. I confirmed both directions.

**Cases list visibility bug (fixed):** `restricted_case_filter` in `src/dispatch/database/service.py` let any non-admin see every restricted case, because the participant check no longer applied to them. I restored the `and_(...)` wrapper, which requires participation for restricted cases. Related tests pass (40 passed). I didn't add a regression test for this one and can add one if you want.

**Verification:** `python -m pytest tests/incident tests/case` (16 passed), and `python -m pytest tests/database tests/case tests/api` (40 passed). I didn't run the full suite.

No commits were made. Changes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc