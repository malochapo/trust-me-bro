## Recap

### Investigation 1: unprotected data-changing routes
- Before my changes, five POST/DELETE handlers in `src/dispatch/case/views.py` and `src/dispatch/incident/views.py` had no `PermissionsDependency`. I confirmed the list by re-parsing the committed (HEAD) versions of both files.
- `case.create_case` and `incident.create_incident` are open on purpose, because anyone may report a case or an incident.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_views.py`. I confirmed the test passes with the fix and fails without it.
- `case.create_case_channel` and `case.create_case_resources` never had a check (commits `ced74f33` and `f08a22b3`). I left them as they were. They are still unprotected and need a decision from you.

### Investigation 2: restricted cases on the cases list
- Commit `42699ebc` flattened `restricted_case_filter` in `src/dispatch/database/service.py` into `open OR restricted OR participant-email`. That showed every restricted case to any user who isn't an admin, owner or manager.
- I restored `and_(restricted, participant-email)`. The `tests/database`, `tests/case` and `tests/incident` suites passed with 41 tests. I added no regression test for this one.
- Six tests in `tests/ai/test_ai_service.py` fail. They fail the same way without my changes, so they are unrelated.

### Signal instance trace and masking
- `redact_raw` in `dispatch.signal.redaction` does the masking. It is called only from `signal_instance_create_flow`. Commit `d2675cf4` introduced it.
- The default masked keys are `password,secret,api_key,session_token,authorization`. Matching is exact and case-insensitive, at any depth.
- The unmasked payload is written to the database. The API commits `raw` as received, and a background worker masks it later.

### Entity extraction bugs
- Commit `beb60cc4` made entity extraction keep only the first JSONPath match. I reverted that one-line change, and `tests/entity` passed.
- Entity extraction ran on the masked payload, so the GitHub token signal's session token became the entity `[REDACTED]`. That grouped unrelated instances under one case through the deduplication filter.
- `find_entities` now skips masked values, and it masks the payload itself before extraction. I added `tests/entity/test_entity_redaction.py`, and its two tests fail without the fix.

Nothing is committed. I changed no existing tests.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4