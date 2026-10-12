**Investigation 1: missing permission checks and the removed check**

I listed every POST/PUT/PATCH/DELETE route in the case and incident views that had no route-level `PermissionsDependency`. Five had none before my changes. Two are intentionally open because anyone may report a case or incident: `case.create_case` and `incident.create_incident`. Three are design gaps that I did not change: `case.create_case_channel`, `case.create_case_resources`, and `incident.delete_custom_event`.

`incident.delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored it in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views.py`, which fails if the check goes missing again. That test fails against the HEAD version of the file and passes with the fix.

**Investigation 2: cases list showing restricted cases to members**

The member branch of `restricted_case_filter` in `src/dispatch/database/service.py` lost its `and_` grouping in commit `42699ebc` ("refactor(database): flatten the restricted case filter"). Without it, any restricted case matched the filter, so members saw cases they were not part of. I restored the grouping, which matches the incident filter. `tests/database/test_service.py` passes 25/25, including the test that had been failing. I checked this at the filter-function level, not through the HTTP endpoint.

**Entity extraction: only the first JSONPath match kept**

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath match in `find_entities`. I removed it. The `tests/entity` failure is fixed. I also need to correct my earlier report: I had called `test_find_entities_with_field_only` a pre-existing failure after checking on HEAD, but HEAD already contained this commit, so that check could not show it predated the change.

**Signal-instance trace**

- The POST handler (`src/dispatch/signal/views.py:70-129`) stores the raw payload, unmasked, and commits it before any processing.
- Masking happens later in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`) via `redact_raw` in `src/dispatch/signal/redaction.py`. Default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`.
- The masking was introduced in `d2675cf4` ("feat(signal): mask sensitive raw fields before processing").
- The unmasked payload is persisted at POST time, so the answer to whether it is ever written to the database is yes.

**Masked values becoming entities**

`[REDACTED]` was extracted as an entity value. Every instance of the signal got the same entity, and the deduplication filter then grouped them. The fix is in `src/dispatch/entity/service.py`: extraction now runs on the redacted payload and skips the mask value. The masking itself is unchanged. The new tests in `tests/entity/test_entity_redaction.py` fail without the fix and pass with it.

**Test status**

- The full suite is 364 passed, 4 skipped, 6 failed. The 6 failures are in `tests/ai/test_ai_service.py`, and I have not investigated them.
- Everything is uncommitted: `src/dispatch/database/service.py`, `src/dispatch/entity/service.py`, `src/dispatch/incident/views.py`, `tests/incident/`, and `tests/entity/test_entity_redaction.py`.
- `ruff` is not installed here, so formatting is unchecked.

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