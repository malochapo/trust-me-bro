**Investigation 1: unprotected write routes.** Five handlers in the case and incident routers changed data without a `PermissionsDependency`, and four of them are intended to stay open. `create_case`, `create_case_channel`, `create_case_resources`, and `create_incident` were added without a check and aren't regressions. The one regression was `incident.delete_custom_event`. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check, and the sibling create and update event routes keep theirs. I restored the check and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again. I confirmed it fails with the fix stashed.

Whether `create_case_channel` and `create_case_resources` should get a check is a design decision that is still open.

**Investigation 2: cases list showing restricted cases.** `restricted_case_filter` in `src/dispatch/database/service.py` lost its `and_` grouping in `42699ebc` ("refactor(database): flatten the restricted case filter"). Restricted cases then matched for every non-admin user. I restored the grouping, which matches the incident filter. `test_restricted_case_filter_with_test_data` failed before the fix (4 cases seen, 3 expected) and passes after.

**Masking and entity extraction.** Signal payloads are masked by `redact_raw` in `src/dispatch/signal/redaction.py`, called from `signal_instance_create_flow`. The default keys are `password`, `secret`, `api_key`, `session_token`, and `authorization`. The unmasked payload is written to the database at API time (`signal/views.py`, commit after `create_instance`) and only overwritten after the processing loop reaches the instance. Commit `beb60cc4` made extraction keep only the first JSONPath match. I reverted that line. The fix also covers the masking gap: `find_entities` now searches a redacted copy of the payload and skips the `[REDACTED]` placeholder, so a masked value can't become an entity. I added `tests/entity/test_entity_redaction.py`, which fails without the change. `beb60cc4` is dated Sep 2 2025, not this week, so if CI went red this week, check for another trigger.

**Test runs.** I ran the targeted suites only: 51 tests for the case filter, incident, and API areas, 11 for `tests/entity`, and 50 passing (1 skipped) across `tests/entity`, `tests/entity_type`, and `tests/signal`. I did not run the full suite.

**Uncommitted.** All changes are uncommitted in the working tree: `src/dispatch/database/service.py`, `src/dispatch/incident/views.py`, `src/dispatch/entity/service.py`, and the new `tests/incident/` and `tests/entity/test_entity_redaction.py` files.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4