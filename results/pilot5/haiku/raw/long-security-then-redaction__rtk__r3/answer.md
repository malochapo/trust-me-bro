Here is the recap for the weekly report. Nothing is committed; the changes are in the working tree.

**1. Permission checks on write routes (case and incident APIs)**
- Five write handlers had no `PermissionsDependency`: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident`, and `incident.delete_custom_event`.
- You confirmed that anyone may report a case or an incident, so the two creation handlers are by design. I did not separately confirm that `create_case_channel` and `create_case_resources` are meant to be open.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored it with one line in `src/dispatch/incident/views.py`.
- A new test, `tests/incident/test_incident_view_permissions.py`, fails if that guard goes missing again. It was checked against the unfixed code.

**2. Restricted cases visible to non-participants**
- Cause: `restricted_case_filter` in `src/dispatch/database/service.py` lost the `and_` wrapper around the restricted-and-participant condition. Every restricted case passed the filter.
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sep 2 2025) introduced it. I restored the wrapper, matching `restricted_incident_filter`.
- `tests/database/test_service.py::test_restricted_case_filter_with_test_data` was failing and now passes. No tests were changed.

**3. Entity extraction keeping only the first match**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath results in `find_entities`. I reverted that line. The entity tests that had been failing now pass.

**4. Masked values becoming entities**
- Cause: the processing flow masks the payload before extracting entities, so a JSONPath pointing at a masked field matched the literal `"[REDACTED]"`. Every instance then got the same entity, and the deduplication filter grouped them. This is inferred from the code; I did not check the database.
- Two other callers, `entity_type/service.py` and `entity_type/flows.py`, extracted from unmasked payloads. This was a second gap.
- Fix: `find_entities` now extracts from `redact_raw(signal_instance.raw)` and skips any match equal to the mask. The masking itself is unchanged.
- New test: `tests/entity/test_entity_masking.py`. It fails against the old code and passes with the fix.

**Test status**
- Full suite: 363 passed, 4 skipped, 6 failed. All 6 failures are in `tests/ai/test_ai_service.py`, and they also failed before these changes. They are not investigated.
- I used the clean venv at `/tmp/sobre-bench-work/run-7df9a02b571a/cleanenv` instead of `python -m pytest` in the project venv, because the project venv's pytest is shadowed and fails on `slack_sdk`.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95