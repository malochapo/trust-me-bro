## Recap

**Investigation 1: unguarded write routes and the incident delete regression**

Before my changes, five data-changing handlers in the case and incident routers had no `PermissionsDependency`. Four are intentionally open, since anyone may report a case or incident. `delete_custom_event` was a regression. Commit `28c21e1e` dropped its `IncidentEventPermission` check. I restored the check in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views.py`, which fails if the check is removed. I confirmed it fails without the fix and passes with it.

**Investigation 2: restricted cases visible to non-participants**

The cases list showed restricted cases to users who were not participants. The cause was `restricted_case_filter` in `src/dispatch/database/service.py`. The restricted-visibility condition had lost its `and_` wrapper, so any restricted case passed the filter. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the wrapper, even though its title describes a refactor. I restored the wrapper. `tests/database/test_service.py` and `tests/case/test_case_service.py` pass with the fix (35 tests). The existing test `test_restricted_case_filter_with_test_data` fails without it.

**Investigation 3: signal payload masking and entity extraction**

- **Masking path:** `POST /api/v1/{organization}/signals/instances` stores the raw payload and commits it before any masking. A background worker later runs `signal_instance_create_flow`, which masks the payload in memory. Masking is done by `redact_raw` in `src/dispatch/signal/redaction.py`. The default masked keys are `password,secret,api_key,session_token,authorization`. The unmasked payload is written to the database at the POST commit and stays there if processing fails. The masking was introduced by `d2675cf4`.
- **Entity extraction bug:** commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath match, so only the first match became an entity. I reverted that line.
- **Masked values as entities:** the masked value `"[REDACTED]"` could become an entity. Instances with masked tokens then shared that entity value and were grouped together by the deduplication filter. Extraction now runs against the redacted payload and skips mask-marker values. The fix is in `src/dispatch/entity/service.py`. The new tests are in `tests/entity/test_entity_masking.py`. They fail when masking is disabled and pass with the fix.

**Test status:** `tests/signal`, `tests/entity` and `tests/entity_type` pass (52 passed, 1 skipped). I did not run the full suite.

**Open items:**
- `src/dispatch/entity_type/flows.py:29` appears broken: it assigns the result of `.append(...)` to `entity_types`, which is `None`. I did not change it.
- All changes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4