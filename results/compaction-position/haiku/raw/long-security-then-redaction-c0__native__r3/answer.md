## Recap

**Unprotected data-changing routes (first review).** Five POST/PUT/PATCH/DELETE handlers had no `PermissionsDependency` on their route. Three are case routes and two are incident routes. Only `delete_custom_event` lost a check that it used to have. The other four were never protected: `create_case` and `create_incident` are the intended open reporting endpoints, and the two case resource routes were added without one.

**Restored check.** `incident.delete_custom_event` regained its `IncidentEventPermission` dependency. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed it. The new test `tests/incident/test_incident_event_permissions.py` fails if the check goes missing again. It fails without the fix and passes with it.

**Restricted cases visible to members.** `restricted_case_filter` in `src/dispatch/database/service.py` had `Case.visibility == restricted` as its own OR term, so any member saw every restricted case. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") caused it. The fix restores the `and_` that ties restricted visibility to participation. `tests/database/test_service.py` passes, including `test_restricted_case_filter_with_test_data`.

**Signal masking and the GitHub token signal.** The payload is masked in `redact_raw` (`src/dispatch/signal/redaction.py`) during signal processing (`src/dispatch/signal/flows.py:60`). Masking runs after the instance is committed, so the unmasked payload is written to the database during the POST. Masked values were also reaching entity extraction. The flow replaced the token with `[REDACTED]`, the entity JSONPath matched that placeholder, and every instance of the signal got the same entity, which the deduplication filter then grouped. The fix is in `find_entities` (`src/dispatch/entity/service.py`): entities are extracted only from the redacted payload, and the placeholder value is skipped. The new test `tests/entity/test_entity_masking.py` covers both the raw and redacted payloads.

**Entity extraction returning only the first match.** Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]`, so only one entity per JSONPath was extracted. I removed the truncation, and `tests/entity` passes.

**Test status.** The full suite gives 363 passed, 4 skipped and 6 failed. The 6 failures are in `tests/ai/test_ai_service.py`, which were failing before any of these changes. I did not investigate them.

**Open items.** Nothing is committed. The changes are in the working tree: the incident permission restore and its test, the restricted-filter fix, the entity fix and its test. Two items are not fixed: the POST still stores the unmasked payload before masking runs, and the masking key list only matches exact names, so `apiKey` and `token` are not masked. You asked me to leave masking as it is, so I did not change either.

```
UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4
```