## Weekly recap

**1. Permission review of the case and incident write routes**
- Five POST/PUT/PATCH/DELETE handlers had no `PermissionsDependency` before my changes. Four are open by design (anyone may report a case or incident, and the case-channel and resource endpoints are unguarded in the code): `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`. I did not confirm the intent of the three non-create endpoints with the team.
- `delete_custom_event` lost its guard in `28c21e1e`. I restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_event_views.py`, which fails if the guard is removed.

**2. Restricted cases visible to non-participants**
- Cause: `restricted_case_filter` in `src/dispatch/database/service.py`. The member branch had restricted cases as a standalone OR term, so any member saw every restricted case.
- Introduced by `42699ebc` (flatten refactor), which removed the `and_` that `b05613b5` (#6155) had added. I restored the `and_`. The existing test `test_restricted_case_filter_with_test_data` now passes, and I did not change any tests.

**3. Entity extraction keeping only the first match**
- `beb60cc4` ("stop at the first JSONPath match") added `[:1]` to the JSONPath match. I removed it. `tests/entity` is green.

**4. Masked tokens grouping unrelated signal instances**
- The flow masked the payload, but the JSONPath still matched the `"[REDACTED]"` placeholder. Every instance produced the same entity, and the dedup on that entity grouped them. I did not trace the dedup filter code, so this grouping step is inferred from the entity mechanism.
- Further, `find_entities` has callers that run on unmasked stored payloads (`entity_type/service.py` and `entity_type/flows.py`).
- Fix in `find_entities`: extraction runs on `redact_raw(...)`, and matches equal to the mask are skipped. The flow's masking is unchanged. Added `tests/entity/test_entity_redaction.py`.
- Trade-off: a field whose real value is exactly `"[REDACTED]"` is no longer extracted as an entity.

**Test status:** full suite is 6 failed, 363 passed, 4 skipped. The 6 failures are in `tests/ai/test_ai_service.py`, which fail because the tokenizer needs network access. They also failed on a clean checkout.

**Uncommitted:** all changes are in the working tree. Nothing has been committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4