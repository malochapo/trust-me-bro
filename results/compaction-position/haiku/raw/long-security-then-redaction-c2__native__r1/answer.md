## Weekly recap

**1. Unprotected data-changing routes (security review)**

I listed the POST, PUT, PATCH and DELETE routes in the case and incident APIs that declare no `PermissionsDependency`. There were five. `create_case` and `create_incident` are open on purpose. `create_case_channel` and `create_case_resources` were never protected, so they are design gaps rather than regressions. I did not change them.

`delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes", 2025-07-14) removed its `IncidentEventPermission` check and changed nothing else. I restored the check in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_event_views.py`. That test fails when the check is missing. I confirmed both states.

**2. Restricted cases visible to members who are not participants**

Members saw restricted cases they did not take part in. In `restricted_case_filter` (`src/dispatch/database/service.py`), commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed an `and_(...)` wrapper. The restricted branch then matched every restricted case, with no participant check. The incident filter was not affected. I restored the wrapper. The existing restricted-case test fails without the fix and passes with it. I did not add a new test for this bug.

**3. Masking of the raw payload on POST `/api/v1/{organization}/signals/instances`**

- The route is `create_signal_instance` in `src/dispatch/signal/views.py`. It stores the raw payload and commits it before any masking runs.
- Masking runs later, in `signal_instance_create_flow`, through `redact_raw` in `src/dispatch/signal/redaction.py`.
- Default masked keys: `password`, `secret`, `api_key`, `session_token`, `authorization`. Matching is exact and case-insensitive. Keys such as `apiKey` are not matched.
- The unmasked payload is written to the database at POST time. The masked copy replaces it only after processing. Instances that fail or never get processed keep the plaintext.
- I did not change any of this. I only traced it.

**4. Entity extraction returning only the first match**

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath match in `find_entities` (`src/dispatch/entity/service.py`). I restored the original line. `tests/entity` is green.

**5. Masked values becoming shared entities**

The "GitHub: Personal access token exposed" signal grouped unrelated cases. Masking replaced the token with the string `"[REDACTED]"`, and the JSONPath extractor turned that string into an entity. Every instance then shared the same entity value, and the deduplication filter grouped them. Entity extraction also runs from `entity_type/flows.py` and `entity_type/service.py` on stored payloads, outside the flow that masks. The fix in `src/dispatch/entity/service.py`:
- `find_entities` masks the payload before extracting, so every caller is covered.
- The extractor skips any match equal to the mask.
- The masking itself is unchanged.

I added `tests/entity/test_entity_redaction.py`. The two bug tests fail without the fix and pass with it.

**Test status:** the full suite gives 365 passed, 4 skipped, 6 failed. The six failures are in `tests/ai/test_ai_service.py`. They need to download a tokenizer, and the sandbox has no network access. Nothing has been committed.

**Corrections:** earlier I said there were six unprotected rows in the review. There were five, and I did not correct that in a message before now.

**Open items I noticed but did not change:**
- `entity_type/flows.py` assigns `None` to `entity_types` because of a misplaced `.append`.
- `create_case_channel` and `create_case_resources` have no permission check.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4