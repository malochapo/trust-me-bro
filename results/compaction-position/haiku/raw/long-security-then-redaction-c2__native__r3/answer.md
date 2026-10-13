## Weekly recap

**1. Write routes without a permission check (case and incident APIs)**

I listed every POST, PUT, PATCH, and DELETE handler in `src/dispatch/case/views.py` and `src/dispatch/incident/views.py` that lacked a `PermissionsDependency`. There are five. Three are case handlers (`create_case`, `create_case_channel`, `create_case_resources`) and two are incident handlers (`create_incident`, `delete_custom_event`). My earlier reply named only two of the case handlers, so this list corrects it. `create_incident` and the three case creation handlers are intentionally open. Only `delete_custom_event` was a regression.

- **Regression:** `DELETE /incidents/{id}/event/{event_uuid}` lost its `IncidentEventPermission` check in commit `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored the check in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_event_views.py`, which fails if the dependency is removed.

**2. Members seeing restricted cases they are not part of**

`restricted_case_filter` in `src/dispatch/database/service.py` had lost its `and_` around the restricted-case clause. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") made any restricted case visible to any member. I restored the participant condition. The existing `test_restricted_case_filter_with_test_data` passes again, and I did not change any tests.

**3. Signal instance path and masking**

A signal instance is stored unmasked by the POST handler, then masked during processing, and only then does entity extraction and filtering run. I traced it through `src/dispatch/signal/views.py`, `service.py`, `flows.py`, and `redaction.py`. The default masked keys are `password`, `secret`, `api_key`, `session_token`, and `authorization`. Matching is exact on the key name, so `apiKey` is not masked.

**4. Entity extraction keeping only the first match**

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath match list. I reverted that line, and `tests/entity` passes.

**5. Masked values becoming entities**

Because the flow masks before extraction, the session token became the entity `[REDACTED]` for every instance, and deduplication grouped unrelated instances on it. `find_entities` now masks the payload itself and skips the mask value, so masked fields never become entities. Three tests in `tests/entity/test_entity_masking.py` cover this. They failed before the fix and pass after it.

**Test status:** 365 passed, 4 skipped, 6 failed. The 6 failures are in `tests/ai/test_ai_service.py`. They try to download a tiktoken encoding and fail without network access. They are unrelated to these changes.

**Not done:** I did not reproduce the deduplication scenario end to end. Existing instances already grouped under `[REDACTED]` still need a separate cleanup. Nothing is committed. The changes are in `src/dispatch/incident/views.py`, `src/dispatch/database/service.py`, `src/dispatch/entity/service.py`, and the new test files under `tests/incident/` and `tests/entity/`.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4