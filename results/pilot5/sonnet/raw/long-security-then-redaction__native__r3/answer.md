## Recap

**1. Permission review (case and incident APIs)**
- Five handlers changed data without a `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, because anyone may report one.
- `create_case_channel` and `create_case_resources` never had a check. I left them alone, but they could be hardened separately.
- `delete_custom_event` was a regression. Commit `28c21e1e` removed its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again.

**2. Restricted cases visible to non-participants**
- Commit `42699ebc` ("flatten the restricted case filter") broke the logic in `restricted_case_filter`. The rule became `open OR restricted OR participant`, so every restricted case matched. I restored the `and_` around the restricted-and-participant condition.
- The existing tests in `tests/database/test_service.py` are unchanged and pass.

**3. Signal instance flow and masking**
- `POST /signals/instances` stores the instance and commits. The background create flow (`signal_instance_create_flow`) later masks the payload, extracts entities, applies the snooze and dedup filters, and then either opens a case or stores the instance without one.
- `redact_raw` masks the payload. It matches key names exactly, ignoring case, at any depth. The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- The unmasked payload is written to the database: the POST route commits it before the flow redacts it. I did not change this, and the fix would be to redact inside `create_instance`.

**4. Entity extraction**
- Commit `beb60cc4` added `[:1]` to the JSONPath match, so only the first match became an entity. I reverted it, and `tests/entity` passes.
- Masked values were also becoming entities, because every instance got the same `[REDACTED]` value. That made the dedup filter group unrelated instances into one case. `find_entities` now masks a copy of the payload first and skips any masked value, and `test_find_entities_never_creates_masked_entity` covers it.

Nothing is committed. The changes are in `src/dispatch/database/service.py`, `src/dispatch/incident/views.py`, `src/dispatch/entity/service.py`, `tests/entity/test_entity_service.py` and the new `tests/incident/`.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4