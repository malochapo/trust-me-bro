## Recap

**1. Permission review (case and incident APIs)**
- Before my changes, five data-changing routes had no `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, because anyone may report a case or incident. I left `create_case_channel` and `create_case_resources` untouched and only reported them.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` removed its `IncidentEventPermission` dependency. I restored it and added `tests/incident/test_incident_event_views.py`, which fails if the check goes missing again.

**2. Restricted cases visible to non-participants**
- Commit `42699ebc` flattened `restricted_case_filter` in `src/dispatch/database/service.py`. It removed the `and_` wrapper, so any restricted case matched the filter for members.
- I restored the `and_`, so a restricted case now shows only to its participants. I did not add a test for this fix.

**3. Signal instance flow and masking**
- `POST /signals/instances` stores the instance and commits it. A scheduled job later runs `signal_instance_create_flow`, which masks the payload, extracts entities, applies filters and either creates a case or stops.
- `redact_raw` in `dispatch.signal.redaction` does the masking. Its default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- The unmasked payload is written to the database first. The masked copy replaces it only when the job later processes that instance. `update_instance` also stores `raw` unmasked.
- The masking was introduced by commit `d2675cf4`.

**4. Entity extraction**
- Commit `beb60cc4` added `[:1]` to the JSONPath matches, so only the first match became an entity. I reverted it, and `tests/entity` passes.
- Grouping of unrelated GitHub-token instances came from the masked value `[REDACTED]` becoming an entity. `find_entities` now extracts from a redacted copy and skips `[REDACTED]` values. I added `test_find_entities_ignores_masked_values`.

**Test state:** `tests/database`, `tests/case`, `tests/incident`, `tests/entity` and `tests/signal` pass. Six `tests/ai` tests fail with or without my changes, and I did not investigate them. Nothing is committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4