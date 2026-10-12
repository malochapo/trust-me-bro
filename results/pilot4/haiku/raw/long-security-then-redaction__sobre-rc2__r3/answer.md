## Recap

**Investigation 1: unguarded mutating routes and the regression**
- Case and incident routers have 13 mutating handlers each. Five declared no `PermissionsDependency`: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident`, and `incident.delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, as you confirmed.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again.
- Open question: `case.create_case_channel` and `case.create_case_resources` have never had a check in any commit I looked at. I did not change them. Someone needs to decide whether they are design choices or gaps.

**Investigation 2: restricted cases visible to non-participants**
- `restricted_case_filter` in `src/dispatch/database/service.py` had `Case.visibility == Visibility.restricted` as a standalone OR term, so any member could see every restricted case.
- Commit `42699ebc` (flatten refactor, 2025-09-02) removed the `and_` grouping that `b05613b5` had added. I restored it. No existing tests were changed.
- Gap: no regression test covers this filter yet.

**Investigation 3: signal payload processing**
- Entry point: `POST /api/v1/{organization}/signals/instances` stores the raw payload with no masking. A scheduled job then runs `signal_instance_create_flow`, which masks the payload and extracts entities.
- Masking is done by `redact_raw` in `src/dispatch/signal/redaction.py`, added in `d2675cf4` (2025-07-03). By default it masks `password`, `secret`, `api_key`, `session_token`, and `authorization`, matched case-insensitively at any depth.
- The unmasked payload is written to the database at the API commit, before any masking runs. The masked version is only committed later, so if the flow fails, the unmasked payload stays in the database.
- **Extraction bug:** commit `beb60cc4` added `[:1]` to the JSONPath matches, so only the first match became an entity. I removed the slice. `tests/entity` passes (11 tests).
- **Masked-entity bug:** `find_entities` extracted entities from the masked payload, so the constant `[REDACTED]` value became an entity. Analysts saw unrelated token exposures grouped into one case because of the deduplication filter. I fixed `find_entities` to mask the payload itself and skip masked values, and added `tests/entity/test_entity_redaction.py`. The new test fails without the fix and passes with it. `tests/entity` and `tests/signal` pass (45 passed, 1 skipped).
- Open: entities already created from masked values are not cleaned up by this fix.

Not done: I did not run the full test suite, and the changes are uncommitted.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4