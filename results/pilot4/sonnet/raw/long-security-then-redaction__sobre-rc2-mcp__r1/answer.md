## Recap

**Investigation 1: unguarded mutating routes and the regression**
- Before my changes, five handlers changed data without a `PermissionsDependency`: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident` and `incident.delete_custom_event`.
- Reporting a case or incident is open on purpose, so `create_case` and `create_incident` are by design. I did not examine the other two case routes, `create_case_channel` and `create_case_resources`, any further. They remain unguarded.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_views_permissions.py`, which fails if the check goes missing.

**Investigation 2: restricted cases visible in the cases list**
- `restricted_case_filter` in `src/dispatch/database/service.py` had lost its `and_(...)` grouping. It read as `open OR restricted OR participant`, so every restricted case matched for non-admin users.
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter") introduced it. I restored `open OR (restricted AND participant)`.

**Investigation 3: signal instance flow and masking**
- `POST /signals/instances` stores the instance and commits it unmasked. A worker later runs `signal_instance_create_flow`. That flow masks the payload with `redact_raw`, extracts entities, applies snooze and deduplication filters, and creates a case unless the instance is filtered, is a canary, or the signal has case creation off.
- The default masked keys are `password`, `secret`, `api_key`, `session_token` and `authorization`. They are configurable with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable.
- The unmasked payload is written to the database. The masking happens only after the worker picks the instance up.
- Masking was introduced by commit `d2675cf4` ("feat(signal): mask sensitive raw fields before processing").

**Investigation 4: entity extraction**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath results, so only the first match became an entity. I reverted that line and `tests/entity` passes.

**Investigation 5: unrelated GitHub token alerts grouped into one case**
- Masked `session_token` values all became the entity `"[REDACTED]"`, so the deduplication filter grouped unrelated instances.
- `find_entities` now skips masked values, and `test_find_entities_skips_masked_values` covers it.

Nothing is committed. Six `tests/ai` tests fail with or without my changes, and I did not investigate them.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95