I parsed both files with Python's `ast` module and checked every `@router.post/put/patch/delete` decorator for a `PermissionsDependency` in its `dependencies=` argument. Five data-changing routes don't declare one. I haven't changed any code.

**`src/dispatch/case/views.py`**
| Method | Path | Function | Line |
|---|---|---|---|
| POST | `""` (create case) | `create_case` | 162 |
| POST | `/{case_id}/resources/conversation` | `create_case_channel` | 236 |
| POST | `/{case_id}/resources` | `create_case_resources` | 260 |

**`src/dispatch/incident/views.py`**
| Method | Path | Function | Line |
|---|---|---|---|
| POST | `""` (create incident) | `create_incident` | 117 |
| DELETE | `/{incident_id}/event/{event_uuid}` | `delete_custom_event` | 503 |

The line numbers are those of the decorators.

I confirmed the decorators for `create_case_channel`, `create_case_resources` and `delete_custom_event` by reading them. None has a `dependencies=` argument at all.

The other POST, PUT, PATCH and DELETE routes in both files do declare a `PermissionsDependency`. The check only looks at the route decorator. It doesn't cover permission checks done inside a function body or by a router-level dependency where the router is mounted (`api.py`).

The riskiest of the five is `delete_custom_event`. It deletes data, and its sibling event routes (`create_custom_event`, `update_custom_event`) are protected by `IncidentEventPermission`.

----- next turn -----

Yes, one of them is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`). I restored its check and added a test. Nothing is committed.

**The regression.** Commit `28c21e1e` ("refactor(incident): tidy custom event routes", 2025-07-14) removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from the route. The commit message calls it a tidy-up, but the diff is a one-line removal of the permission check. The route had that check from when it was added, and it is the same check the neighbouring create, update and export event routes still use.

**The other two were never protected.** `create_case_channel` and `create_case_resources` have had no `PermissionsDependency` since the commits that added them (`ced74f33` and `f08a22b3`). They are missing a check, but they are not regressions. Whether they should have one is a separate decision for you.

**The fix.** I put the original `dependencies=[...]` line back in `src/dispatch/incident/views.py`.

**The test.** `tests/incident/test_incident_view_permissions.py` looks up the DELETE route on the incident router and asserts that `IncidentEventPermission` is among its permission dependencies.
- **With the fix:** it passes.
- **With the fix stashed:** it fails.

I ran only this new test, not the full suite.

----- next turn -----

**Cause.** In `restricted_case_filter` (`src/dispatch/database/service.py`), the filter's `or_()` had `Case.visibility == restricted` as its own alternative, separate from the participant-email check. So any restricted case matched for every non-admin user, whether or not they take part in it. This hits anyone who isn't admin, owner or manager, and the security-team member is one of them.

**Introduced by.** Commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). It removed the `and_(restricted, email == current_user.email)` wrapper and left the two conditions as separate `or_` branches. The commit message calls it a refactor, but the change broadens access.

**Fix.** I put the `and_()` back, so a restricted case shows only to its participants. This matches `restricted_incident_filter`, which already had the correct form.

**Tests.** I didn't touch the existing tests. `tests/database` and `tests/case` pass (40 passed), but I didn't run the full suite. I also didn't add a test for this: I did not check whether the existing tests cover the restricted-case filter. I can add one that fails with the flattened version if you want it.

Both this fix and the earlier permission fix are uncommitted in the working tree.

----- next turn -----

## Recap

**Audit.** I checked every POST, PUT, PATCH and DELETE route in `case/views.py` and `incident/views.py` for a `PermissionsDependency` in its decorator. Five had none:
- `create_case` and `create_incident` are open on purpose, since anyone may report a case or an incident.
- `create_case_channel` and `create_case_resources` have never had a check. They were added without one in `ced74f33` and `f08a22b3`, so they are missing a check but not regressions. Whether they should get one is still open.
- `delete_custom_event` was a regression.

**Permission regression.** Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `IncidentEventPermission` from `DELETE /{incident_id}/event/{event_uuid}`. I restored it and added `tests/incident/test_incident_view_permissions.py`. The test passes with the fix and fails without it.

**Visibility bug.** Commit `42699ebc` ("flatten the restricted case filter") turned `and_(restricted, participant email)` into two separate `or_` branches. Every restricted case therefore matched for every non-admin user. I restored the `and_()` in `restricted_case_filter` in `src/dispatch/database/service.py`. `tests/database` and `tests/case` pass (40 passed). I did not run the full suite or add a test for the visibility filter.

Both fixes are in the working tree and not committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc