## Recap

**1. Permission audit (case and incident APIs)**
I listed every POST, PUT, PATCH, and DELETE handler in the case and incident routers that had no `PermissionsDependency`. Two of the five are intentional open reporting routes: `create_case` and `create_incident`. The other three are not all regressions:
- `create_case_channel` and `create_case_resources` never had a check, so they are gaps from when they were added, not regressions.
- `delete_custom_event` lost its `IncidentEventPermission` check in `28c21e1e` ("refactor(incident): tidy custom event routes"). That commit was labelled a refactor, and it only removed the `dependencies=` line.

I restored the check on `delete_custom_event` and added `tests/incident/test_incident_event_permissions.py`. The test fails when the check is removed and passes with it. I left the two unguarded case resource routes alone; they need a decision on whether they should be guarded.

**2. Restricted cases visible to non-participants**
`restricted_case_filter` in `src/dispatch/database/service.py` lost its `and_(...)` wrapper in `42699ebc` ("refactor(database): flatten the restricted case filter"). Any restricted case then matched for any non-admin user. I restored the wrapper. The existing `tests/database/test_service.py::test_restricted_case_filter_with_test_data` fails on the buggy version and passes with the fix, so no new test was needed.

**3. Signal instance path and masking**
A signal instance is accepted by `POST /signals/instances`, which stores the raw payload and returns it. Processing runs later. In `signal_instance_create_flow`, `redact_raw` masks the payload before entity extraction, and the flow then either filters the instance or creates a case. Masking matches key names case-insensitively, at any depth, and the default keys are `password, secret, api_key, session_token, authorization`. The unmasked payload is written to the database when the instance is created, and it is returned in the create response.

**4. Entity extraction returns only the first match**
`beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath lookup, so only the first match became an entity. I removed the slice. `tests/entity` was red before and passes now.

**5. GitHub PAT signal grouping**
When a JSONPath matched a masked field, the placeholder `"[REDACTED]"` became an entity value. Every such instance then shared that entity and was deduplicated into one case. `find_entities` now masks the payload itself before extraction and skips any value equal to the mask. Masking is unchanged. The new test is `tests/entity/test_entity_masked_values.py`, and it fails without the fix.

**Test results:** `python -m pytest tests/entity tests/signal tests/entity_type tests/incident tests/case tests/database -q` gives 91 passed, 1 skipped.

**Uncommitted:** the changes listed above are in the working tree, along with the two new test files. Nothing is committed.

**Open item:** the two case resource routes still have no permission check.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4