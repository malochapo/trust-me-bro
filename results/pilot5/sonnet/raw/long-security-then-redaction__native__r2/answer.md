## Recap

**1. Unprotected data-changing routes**
- Before my changes, five handlers in `case/views.py` and `incident/views.py` changed data without a `PermissionsDependency`. I re-checked this against the committed `HEAD` versions of both files.
- Four are open or unconfirmed: `create_case`, `create_case_channel`, `create_case_resources` and `create_incident`. You said anyone may report a case or an incident.
- The fifth was a regression. Incident `delete_custom_event` lost its `IncidentEventPermission` check in commit `28c21e1e`.
- I restored the check and added `tests/incident/test_incident_route_permissions.py`. It covers the four incident event routes, and I saw it fail without the fix.

**2. Restricted cases leaking into the cases list**
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter") flattened the nested `and_` in `restricted_case_filter`.
- Every non-admin then matched every restricted case.
- I restored the `and_` grouping. The existing tests are untouched, and `tests/database` and `tests/case` pass.
- I added no new test for this filter.

**3. Signal instance flow and masking**
- `POST .../signals/instances` stores the instance and its raw payload as received, then commits.
- A separate worker (`main_processing_loop`) later calls `signal_instance_create_flow`.
- The flow masks the payload with `redact_raw`, extracts entities, filters (snooze, then dedup), and either opens a case or stops.
- Masking only matches exact key names, case-insensitively. The unmasked payload is written to the database at request time and stays there until the worker processes the instance.

**4. Entity extraction**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath matches, so only the first match became an entity.
- I removed it, and `tests/entity` passes.

**5. Masked values grouping unrelated cases**
- Entities were extracted from the already-masked payload, so every instance got the entity `"[REDACTED]"`. The dedup filter then grouped unrelated instances into one case.
- `find_entities` now skips masked values, and I added `test_find_entities_skips_masked_values`. It fails without the fix.
- Masking itself is unchanged, and the first signal-masking commit is `d2675cf4`.

I didn't run the full suite, and nothing is committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965
VISIBILITY_BUG: 42699ebc7cdb
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435
MASKING_COMMIT: d2675cf4b078