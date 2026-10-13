## Weekly recap

**1. Unprotected mutating routes (security review)**
- Five data-changing handlers had no `PermissionsDependency` at the start: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident`, and `incident.delete_custom_event`.
- `create_case` and `create_incident` are open on purpose. The other three are not.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_views_permissions.py`, which fails if it goes missing again.
- `case.create_case_channel` and `case.create_case_resources` have had no check since they were added (`ced74f33`, `f08a22b3`). I reported them as gaps and did not change them.

**2. Cases list showing restricted cases to non-participants**
- Cause: `restricted_case_filter` in `src/dispatch/database/service.py` lost its `and_` grouping, so any restricted case matched for any user.
- Introduced by `42699ebc` ("refactor(database): flatten the restricted case filter"). The correct version came from `b05613b5` (#6155).
- Fix: restored the `and_`. `test_restricted_case_filter_with_test_data` fails without the fix and passes with it. No existing tests changed.

**3. Entity extraction returning only the first match**
- `beb60cc4` ("perf(entity): stop at the first JSONPath match") added a `[:1]` slice in `find_entities`. I reverted that line. `tests/entity` passes (11 passed).

**4. Masked values becoming entities**
- Masking runs in the signal flow before entity extraction. A JSONPath aimed at a masked key read `"[REDACTED]"`, which became a shared entity. Instances with that entity were then deduplicated into one case.
- Fix: `find_entities` now masks the payload itself with `redact_raw` and skips any `"[REDACTED]"` value. This covers every caller, including the entity-type paths that run on unmasked payloads. The masking itself is unchanged.
- New test: `tests/entity/test_entity_redaction.py`. It fails without the fix. `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**5. Signal payload masking (trace only, no code changes)**
- Masking happens in `redact_raw`, called from `signal_instance_create_flow`, which runs in the `signals process` loop, not in the POST handler.
- The POST handler commits the unmasked payload. The masked version replaces it only when the flow commits.

**Caveats**
- I did not run the full test suite, only the targeted suites above.
- The changes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4