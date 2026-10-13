## Recap

**Access review (case and incident API)**
- Five data-changing routes had no `PermissionsDependency`. Two are reporting endpoints that are open by design (`case.create_case`, `incident.create_incident`). The other three were not protected from when they were added: `case.create_case_channel`, `case.create_case_resources` and `incident.delete_custom_event`.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` ("tidy custom event routes") removed its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again.
- The two case routes had no check from the start (`ced74f33`, `f08a22b3`), so I left them. Whether they should require edit rights is a decision for the team.

**Restricted cases visible to non-participants**
- `restricted_case_filter` in `src/dispatch/database/service.py` let members see every restricted case. Commit `42699ebc` ("flatten the restricted case filter") dropped the `and_` that required participation. I restored it. The existing test went from `assert 4 == 3` to passing.

**Signal trace (POST `/signals/instances`)**
- The API stores the raw payload and commits it. Masking happens later, in `signal_instance_create_flow`, when the `signals process` worker runs. The masked payload then overwrites the stored one.
- `redact_raw` in `src/dispatch/signal/redaction.py` does the masking. Default keys are `password, secret, api_key, session_token, authorization`. Matching is exact on the key name, so variants such as `apiKey` are not masked.

**Entity extraction and shared "[REDACTED]" entities**
- Commit `beb60cc4` added `[:1]` to the JSONPath match, so only the first match became an entity. I removed the slice. `tests/entity` is green again.
- Masked values became entities because the JSONPath matched the `"[REDACTED]"` string. Every instance then got the same entity, and the dedup filter grouped them. `find_entities` now masks the payload itself and skips masked values. This covers the stored-instance path in `entity_type/service.py`, which bypassed the flow's masking. The new test is `tests/entity/test_entity_redaction.py`.
- Still open: entities already created from `[REDACTED]` need a data cleanup. `entity_type/flows.py:29` also has a separate bug, where `append()` returns `None` and the block after it never runs.

Nothing is committed. Earlier changes and the new tests are in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4