Both investigations are finished. Nothing is committed, and the working tree has these uncommitted changes: `src/dispatch/database/service.py`, `src/dispatch/entity/service.py`, `src/dispatch/incident/views.py`, plus the new test files `tests/incident/` and `tests/entity/test_entity_masking.py`.

**Investigation 1: unprotected mutating routes and restricted-case visibility**
- Five mutating handlers had no `PermissionsDependency` before my changes. Three case handlers (`create_case`, `create_case_channel`, `create_case_resources`) and one incident handler (`create_incident`) are open on purpose, since anyone may report a case or incident. The incident `delete_custom_event` handler was a regression: commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_event_permissions.py`, which fails if the check is removed again.
- The cases list showed restricted cases to members who don't participate. In `restricted_case_filter` (`src/dispatch/database/service.py`), commit `42699ebc` ("refactor(database): flatten the restricted case filter") replaced the `and_` (restricted AND participant email matches) with a bare restricted OR branch. I restored the `and_`.

**Investigation 2: entity extraction**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added a `[:1]` slice, so only the first match per entity type became an entity. I removed the slice; `tests/entity` passes again.
- Masking is in `redact_raw` (`src/dispatch/signal/redaction.py`), added in `d2675cf4` ("feat(signal): mask sensitive raw fields before processing", 2025-07-03). The default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`.
- The payload is stored unmasked: the POST handler commits the raw payload before the background processing that masks it. The window stays open until processing runs, and if processing fails before the filter commit, the row keeps the unmasked payload.
- The grouping bug: the masked placeholder `"[REDACTED]"` became an entity value, so unrelated instances with redacted tokens were deduplicated together. Entity extraction now searches a masked copy and skips the placeholder value, with tests in `tests/entity/test_entity_masking.py` (both fail on the committed code).

**Test status:** the full suite gives 364 passed, 4 skipped, 6 failed. The 6 failures are in `tests/ai/test_ai_service.py` and need network access to download a tiktoken encoding, which this sandbox doesn't have.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95