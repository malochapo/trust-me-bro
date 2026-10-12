## Recap

**1. Unguarded mutating routes and the incident regression**

I listed the POST, PUT, PATCH and DELETE routes in `case/views.py` and `incident/views.py` that have no `PermissionsDependency`. Four were unguarded before my changes, and one was a regression:

- `create_case`, `create_incident`: open by design, since anyone may report a case or an incident.
- `create_case_channel`, `create_case_resources`: unguarded but never removed by a commit. I flagged these as an open design question and did not change them.
- `delete_custom_event` (incident): its permission check was removed by `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` and added `tests/incident/test_incident_event_permissions.py`. The test fails on the regressed code and passes with the fix.

**2. Cases list showing restricted cases to non-participants**

`restricted_case_filter` in `src/dispatch/database/service.py` lost its `and_` guard in `42699ebc` ("refactor(database): flatten the restricted case filter"). The restricted clause then matched every restricted case. The original guard came from `b05613b5` (sec(authz)). I restored it so a restricted case matches only when the user is a participant. The existing `test_restricted_case_filter_with_test_data` catches the regression.

**3. Signal instance flow: masking and entity extraction**

- **Where masking happens:** `redact_raw` in `src/dispatch/signal/redaction.py`, called from `signal_instance_create_flow` in `src/dispatch/signal/flows.py` before entity extraction. Masking was introduced in `d2675cf4` ("feat(signal): mask sensitive raw fields before processing").
- **Default keys:** `password, secret, api_key, session_token, authorization` (`SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`).
- **Unmasked payload in the database:** yes. `create_instance` commits the raw payload, and the POST response returns it. The worker overwrites the column with the masked version later, so the plaintext persists until processing.
- **Extraction bug:** `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath lookup, so only the first matching field became an entity. I reverted that line. `tests/entity` passes (11 tests).
- **Masked values as entities:** the flow masks the payload before extraction, so a JSONPath pointing at a masked key matched the placeholder `"[REDACTED]"`. Every instance then got the same entity, and the deduplication filter grouped them. Extraction now skips values equal to `MASK`, and `tests/entity/test_entity_masking.py` covers this. `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**Open items:**
- Entities already created from masked values stay in the database and need a separate cleanup.
- The two unguarded case routes still need a decision.
- Nothing is committed. Uncommitted changes: the incident permission restore and its test, the cases-list visibility fix, the entity revert, the masked-value check, and the new test files.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4