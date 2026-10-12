## Recap

**Investigation 1: permission checks (security review)**
- Five data-changing handlers had no `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, because anyone may report a case or an incident.
- `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") dropped its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_view_permissions.py`, which fails if the check goes missing again.
- `create_case_channel` and `create_case_resources` never had a check, so they are not regressions. They are a possible hardening item.

**Investigation 2: restricted cases shown to non-participants**
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_` in `restricted_case_filter`. Every restricted case then matched for non-admin users. I restored the `and_`, and the existing tests are untouched.

**Investigation 3: signal masking**
- `redact_raw` in `dispatch.signal.redaction` masks values to `[REDACTED]`, matching keys case-insensitively and exactly, at any depth. Commit `d2675cf4` introduced it.
- The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`. They can be overridden with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable.
- The API view commits the payload as received. Masking only happens later, in the worker's `signal_instance_create_flow`. So the unmasked payload is written to the database, briefly.

**Investigation 4: entity extraction**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") kept only the first match. I reverted the line, and `tests/entity` is green again.
- Separately, masked tokens all became the same `[REDACTED]` entity, which grouped unrelated GitHub token instances into one case. `find_entities` now skips masked values, and `tests/entity/test_entity_masked_values.py` covers it.

All changes are uncommitted. I only ran `tests/database`, `tests/case`, `tests/entity` and `tests/signal`, not the full suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95