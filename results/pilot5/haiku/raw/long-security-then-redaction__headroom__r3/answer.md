Here is the recap for the weekly report. Nothing is committed, and the full test suite has not been run. Only the test directories I touched were run.

**1. Unguarded data-changing routes and the restored check**
- Before my changes, five POST/PUT/PATCH/DELETE handlers had no `PermissionsDependency`: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident`, and `incident.delete_custom_event`.
- `incident.create_incident` is open on purpose, since anyone may report an incident. `case.create_case` is also open by design, and the report-wide intent note covers it.
- `case.create_case_channel` and `case.create_case_resources` never had a check, so they are not regressions. Whether they should carry `CaseEditPermission` is still an open question.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") deleted its `IncidentEventPermission` dependency. I restored it in `src/dispatch/incident/views.py`. A new test, `tests/incident/test_incident_event_views.py`, fails if the check goes missing again.

**2. Cases list showing restricted cases to non-participants**
- The cause was `restricted_case_filter` in `src/dispatch/database/service.py`. The `and_` tying a restricted case to the user's participation had been dropped. Every restricted case then matched for non-admin roles.
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter") introduced it. It was framed as a cleanup. I restored the `and_` to match the incident filter.
- `tests/database/test_service.py::test_restricted_case_filter_with_test_data` fails on the buggy version and passes with the fix. No existing tests were changed.

**3. Entity extraction keeping only the first match**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath match, so only one entity per type was kept.
- I removed the slice in `src/dispatch/entity/service.py`. `tests/entity` failed before and passes after.

**4. Masked values becoming entities**
- Signal instances from the "GitHub: Personal access token exposed" signal were grouping because the masked value `"[REDACTED]"` became an entity. Every instance then shared that entity, and the dedup filter grouped them.
- The fix is in `find_entities` (`src/dispatch/entity/service.py`). It matches JSONPaths against the redacted payload and skips any match equal to the mask. I left the masking itself unchanged.
- New test: `test_find_entities_never_extracts_masked_values`. It fails without the guard. `tests/entity`, `tests/signal`, and `tests/entity_type` give 50 passed and 1 skipped.

**5. Masking**
- The redaction lives in `redact_raw` in `src/dispatch/signal/redaction.py`. It is called from the signal instance create flow, `signal_instance_create_flow`.
- The unmasked payload is written to the database. `create_instance` commits the raw payload before the flow masks it, and it stays unmasked until the scheduled job processes the row.
- Masking was introduced in commit `d2675cf4` ("feat(signal): mask sensitive raw fields before processing").

**Uncommitted changes in the working tree**
- `src/dispatch/database/service.py`
- `src/dispatch/entity/service.py`
- `src/dispatch/incident/views.py`
- `tests/incident/` (new)
- `tests/entity/test_entity_service.py` (one test appended)

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4