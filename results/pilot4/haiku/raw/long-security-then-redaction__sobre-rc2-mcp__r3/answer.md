**Permissions audit and regression (incident custom events)**
- Audited the write routes (POST, PUT, PATCH, DELETE) in the case and incident views at the starting commit. Five had no `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`, and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, since anyone may report a case or incident. `create_case_channel` and `create_case_resources` were never gated, so they aren't regressions. Whether they should be gated is still open.
- `delete_custom_event` was a regression: commit `28c21e1e` ("refactor(incident): tidy custom event routes") dropped its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again. Verified that it fails with the check removed and passes when restored.

**Restricted cases in the cases list**
- Members could see restricted cases they weren't participants in. In `restricted_case_filter` (`src/dispatch/database/service.py`), the restricted-visibility term stood alone in the OR, so it matched without the participant check. The incident filter already groups the two terms with `and_`.
- Introduced by `42699ebc` ("refactor(database): flatten the restricted case filter"), which removed the `and_` from the original fix in `b05613b5`. Restored the grouping. The existing `test_restricted_case_filter_with_test_data` failed (`got 4`) and now passes. No tests were changed.

**Signal payload masking and entity extraction**
- Tracing `POST /api/v1/{organization}/signals/instances`: the handler stores the raw payload without masking and returns it unmasked. The masking runs later in the scheduled processing flow, before entity extraction and before the case or filter decision. The unmasked payload does reach the database until that run commits the masked copy.
- Entity extraction (`find_entities`) returned only the first JSONPath match, because of `beb60cc4` ("perf(entity): stop at the first JSONPath match"). I removed the slice; `tests/entity` passes.
- Masked values could become entities: the `[REDACTED]` placeholder matched by a JSONPath became a shared entity, so unrelated instances were grouped by dedup. I made `find_entities` mask the payload itself and skip mask-valued matches, which also covers older unmasked payloads. Added `tests/entity/test_entity_masking.py` (3 tests, 2 of which fail without the fix). I did not reproduce the full ingest flow end to end.

**Test results:** `python -m pytest tests/entity tests/signal tests/database tests/case tests/incident` gives 87 passed, 1 skipped.

**Status:** all changes are uncommitted: `src/dispatch/database/service.py`, `src/dispatch/incident/views.py`, `src/dispatch/entity/service.py`, and the new files under `tests/incident/` and `tests/entity/test_entity_masking.py`.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95