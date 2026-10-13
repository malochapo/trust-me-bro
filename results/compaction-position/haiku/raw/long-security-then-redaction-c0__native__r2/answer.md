The recap is below. Nothing is committed yet, and all the changes are in the working tree.

**1. Permission review (write routes without a `PermissionsDependency`)**
Five handlers changed data without a declared permission: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`, and `delete_custom_event`. Reporting a case or incident is open by design. The two case resource routes were never protected, so they're a gap to decide on, not a regression. `delete_custom_event` was a regression: commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again. It fails on the pre-fix file and passes after the restore.

**2. Restricted cases visible to non-participants**
The cases list leaked restricted cases to members who were not participants. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_(...)` grouping in `restricted_case_filter`. That turned the restricted branch into a match for every non-admin. I restored the grouping. `test_restricted_case_filter_with_test_data` failed with 4 where 3 were expected, and passes now.

**3. Entity extraction keeping only the first match**
Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath results, so each entity type produced at most one entity. I removed the slice. `tests/entity` was red and is green now. The performance goal of that commit was not addressed; if it still matters, it needs its own design.

**4. Masked tokens grouping unrelated instances**
Masking happened before extraction, so every masked instance produced the entity value `"[REDACTED]"`, and the deduplication filter grouped them. A direct call to `find_entities` on an unmasked payload also extracted the raw secret. I changed `_find_entities_by_jsonpath_expression` to extract from `redact_raw(...)` and skip the placeholder. The masking code is unchanged. The new test `tests/entity/test_entity_masking.py` failed before the fix and passes now.

**Test status:** `tests/entity`, `tests/signal`, `tests/case`, `tests/incident`, and `tests/database` pass (85 passed, 1 skipped). I did not run the full suite.

**Open items**
- Unmasked payloads are still written to the database when the instance is created. The processor overwrites them with the masked copy later, and a failed instance stays unmasked. I did not change this.
- Entities created before the fix may still hold the value `"[REDACTED]"`. Those need a cleanup before any deduplication rule on them is trusted.
- The two case resource routes still have no permission check.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4