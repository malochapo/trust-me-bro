Five data-changing routes across the two files have no `PermissionsDependency` in their route definition. I found them by parsing every `@router.post/put/patch/delete` decorator in both files with Python's `ast` module, not by reading the files by eye.

**Case API (`src/dispatch/case/views.py`)**

| Line | Route | Handler |
|---|---|---|
| 162 | `POST ""` | `create_case` |
| 236 | `POST /{case_id}/resources/conversation` | `create_case_channel` |
| 260 | `POST /{case_id}/resources` | `create_case_resources` |

**Incident API (`src/dispatch/incident/views.py`)**

| Line | Route | Handler |
|---|---|---|
| 117 | `POST ""` | `create_incident` |
| 503 | `DELETE /{incident_id}/event/{event_uuid}` | `delete_custom_event` |

The other POST, PUT, PATCH and DELETE routes in both files declare a `PermissionsDependency`.

The check only looks at the route decorators. I didn't check whether these handlers or the router enforce authorization some other way, such as a router-level dependency in `api.py`, so some of the five may be covered elsewhere. I haven't changed any code.

----- next turn -----

Yes, one of the three is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`) in `src/dispatch/incident/views.py`.

- **Regression:** commit `28c21e1e`, "refactor(incident): tidy custom event routes", removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from that route. It deleted one line, and the commit message doesn't mention a permission change. It was the only unprotected route that had previously been protected.
- **Fix:** I restored that exact line to the route. The diff is one added line in `src/dispatch/incident/views.py`.
- **Test:** I added `tests/incident/test_incident_views.py`. It finds the DELETE route on the incident router and asserts that `IncidentEventPermission` is among its `PermissionsDependency` classes. It passes with the fix. With the fix stashed it fails, so it would catch the check going missing again. I ran only this one test file, not the full suite.
- **Not regressions:** the two case routes, `POST /{case_id}/resources/conversation` and `POST /{case_id}/resources`, have no permission dependency in the commits that introduced them (`ced74f33` and `f08a22b3`). They are older gaps, not something removed later. They let any caller create a case's conversation channel or resources, so they may deserve a `CaseEditPermission`. I left them alone since you only asked about regressions.

----- next turn -----

The cause is in `restricted_case_filter` in `src/dispatch/database/service.py`. It was introduced by commit `42699ebc`, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2025-09-02).

That commit changed the case visibility filter from this:

```python
Case.visibility == Visibility.open,
and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email),
```

to this:

```python
Case.visibility == Visibility.open,
Case.visibility == Visibility.restricted,
IndividualContact.email == current_user.email,
```

The `or_` then matched every restricted case for everyone, so non-admin users such as the security team member saw all restricted cases, including ones they don't take part in. The "flatten" refactor changed the logic rather than just the shape of the code.

I restored the `and_(...)` around the restricted condition. That brings it back to the version in `b05613b5` and in line with `restricted_incident_filter`, which is still correct. I didn't touch any tests. The `tests/database` and `tests/case` suites pass (40 tests), but I didn't run the whole suite. I also didn't add a test for this filter, since you asked me not to change the existing ones. Say so if you want a new regression test for it.

----- next turn -----

## Recap

**Unprotected routes at the start.** Five routes changed data without a `PermissionsDependency`.
- Three are open by design or older gaps: `create_case` and `create_incident` are open on purpose, since anyone may report a case or an incident. `create_case_channel` and `create_case_resources` never had a check. They may deserve a `CaseEditPermission`, but I left them alone.
- One was a regression: `incident.delete_custom_event` lost `IncidentEventPermission` in commit `28c21e1e`. I restored the check and added `tests/incident/test_incident_views.py`. The test fails without the fix and passes with it.

**Restricted cases visible to everyone.** Commit `42699ebc` ("flatten the restricted case filter") changed `restricted_case_filter` in `src/dispatch/database/service.py`. It dropped the `and_` around the restricted condition. That made every restricted case match for non-admin users, whether or not they took part. I put the `and_` back. The `tests/database` and `tests/case` suites pass (40 tests). I didn't run the full suite, and I added no regression test for this filter.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc