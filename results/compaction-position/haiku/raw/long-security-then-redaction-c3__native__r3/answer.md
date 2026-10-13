**Investigation 1: unprotected write routes and the regression**

- Listed the POST, PUT, PATCH and DELETE routes in the case and incident APIs that had no `PermissionsDependency`. Five handlers qualified: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open by design, since anyone may report a case or incident.
- `create_case_channel` and `create_case_resources` were never protected. They were added without a check in `ced74f33` and `f08a22b3`, so they are not regressions. I left them unchanged and flagged them for a decision.
- `delete_custom_event` was a regression. Commit `28c21e1e` removed its `IncidentEventPermission` check. I restored it in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views.py`. That test fails if the check is removed again; I confirmed it fails without the check and passes with it.

**Investigation 2: restricted cases visible to non-participants**

- The cases list leaked restricted cases. `restricted_case_filter` in `src/dispatch/database/service.py` let any restricted case through without a participant check, because the restricted term sat outside the `and_` grouping.
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed that grouping. I restored it. No tests were changed, and `tests/database/test_service.py` plus `tests/case` pass (40 passed).

**Investigation 3: signal masking, entity extraction, and grouping**

- **Tracing masking:** `POST /api/v1/{organization}/signals/instances` stores the raw payload with `create_instance` and commits it before any masking runs. The processing loop then calls `signal_instance_create_flow`, which masks the payload with `redact_raw` (`src/dispatch/signal/redaction.py`) before entity extraction and filtering.
- **Unmasked payload in the database:** yes. The POST commit stores the unmasked payload, and the redacted copy only overwrites it when the processing loop reaches that instance.
- **Extraction bug:** commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath matches in `find_entities`. I removed it, and `tests/entity` passes.
- **Grouping bug:** the masked placeholder `"[REDACTED]"` was a string, so it passed extraction and became an entity. Every instance with a masked token then shared that entity, and deduplication grouped them. I changed `_find_entities_by_jsonpath_expression` to skip matches equal to `MASK`, and added `test_find_entities_never_extracts_masked_values`. The new test fails without the fix. With the fix, `tests/entity` and `tests/signal` give 44 passed, 1 skipped.

**Open items:**
- All changes are uncommitted, including the new tests.
- Whether `create_case_channel` and `create_case_resources` should get a permission check is a decision for you.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4