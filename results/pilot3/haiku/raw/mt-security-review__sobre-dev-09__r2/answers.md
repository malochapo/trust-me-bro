Five mutating routes have no `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST /{organization}/cases` — `create_case` (line 162)
2. `POST /{organization}/cases/{case_id}/resources/conversation` — `create_case_channel` (line 236)
3. `POST /{organization}/cases/{case_id}/resources` — `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST /{organization}/incidents` — `create_incident` (line 117)
5. `DELETE /{organization}/incidents/{incident_id}/event/{event_uuid}` — `delete_custom_event` (line 503)

The other 22 mutating routes (13 in case, 9 in incident) declare a `PermissionsDependency`. I checked the parent routers in `src/dispatch/api.py`. `authenticated_organization_api_router` only adds `get_organization_path`, which is not a permission check, so it doesn't cover these routes.

I made no code changes.

----- next turn -----

I restored the one regression I found, added a test for it, and left the two other unguarded routes alone.

**Regression fixed:** `DELETE /{organization}/incidents/{incident_id}/event/{event_uuid}` (`delete_custom_event`, `src/dispatch/incident/views.py`). Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]`. Every other custom-event route in the incident API still has that check. I restored the line exactly as it was.

**Not regressions:**
- `POST /cases/{case_id}/resources` (`create_case_resources`) was added in `f08a22b3` without a check. It was never guarded.
- `POST /cases/{case_id}/resources/conversation` (`create_case_channel`) was added in `ced74f33` without a check. It was never guarded.

These two may be worth a look, but I didn't change them because no check was ever removed. The case-level create route and the incident-level create route are open by design, as you said.

**Test:** `tests/incident/test_incident_event_permissions.py`. It inspects the router and asserts that the DELETE custom-event route carries a `PermissionsDependency` that includes `IncidentEventPermission`. I ran it both ways:
- With the fix: passes.
- Without the fix (stashed): fails.

**Full suite:** `python -m pytest` gives 360 passed, 8 failed, 4 skipped. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py` (1), and `tests/entity/test_entity_service.py` (1). They fail identically with my change stashed, so they predate it. I didn't investigate their causes.

----- next turn -----

The cause is in `restricted_case_filter` (`src/dispatch/database/service.py`). Its OR clause had a bare `Case.visibility == Visibility.restricted` term, so every restricted case matched for any non-admin user, whether or not they were a participant. I wrapped that check back in `and_` with the participant match, which is how the incident filter already does it.

**Introduced by:** `42699ebc` ("refactor(database): flatten the restricted case filter", 2025-09-02). It removed the `and_` wrapper while flattening the OR clause.

**Verification:**
- `tests/database/test_service.py` passes (25/25). `test_restricted_case_filter_with_test_data` was one of the pre-existing failures and now passes. I didn't change any tests.
- Full suite: 361 passed, 7 failed, 4 skipped. Before this fix it was 360 passed, 8 failed. The 7 remaining failures are the same pre-existing ones in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py`, which I haven't investigated.

I didn't add a new regression test for this, because the existing `test_restricted_case_filter_with_test_data` already covers the case. The incident-side regression test from before is still in `tests/incident/`.

----- next turn -----

## Review recap

**Unprotected endpoints (first answer):** Five handlers change data without a `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`, and `delete_custom_event` (incident). `create_case` and `create_incident` are open on purpose, since anyone may report. The two case routes were added without a check and were never guarded, so I left them alone. Please confirm whether they should be guarded.

**Restored check:** `delete_custom_event` in the incident API had its `IncidentEventPermission` check removed in `28c21e1e`. I restored it and added `tests/incident/test_incident_event_permissions.py`. The test fails without the fix and passes with it.

**Restricted-case visibility bug:** `restricted_case_filter` in `src/dispatch/database/service.py` let non-admin users see every restricted case. Its OR clause lacked the `and_` that ties restricted visibility to participation. Commit `42699ebc` removed that wrapper. I restored it. `test_restricted_case_filter_with_test_data` now passes. No tests were changed.

**Test suite:** 361 passed, 7 failed, 4 skipped. The 7 failures are in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py`. They fail on the untouched code too, and I haven't investigated them.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289