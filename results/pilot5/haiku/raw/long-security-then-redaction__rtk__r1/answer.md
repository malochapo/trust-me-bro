Recap of today's work. Nothing is committed. All the fixes are uncommitted in the working tree.

**1. Write routes without a permission check (case and incident APIs)**

At HEAD, five write handlers had no `PermissionsDependency`: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident`, and `incident.delete_custom_event`. The first four are open by design, since anyone may report a case or an incident. The two case resource routes never had a check, so they are not regressions.

`incident.delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes", 2025-07-14) removed its `IncidentEventPermission` line. I restored the check in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views_permissions.py`. The test fails when the check is removed and passes with it restored.

**2. Cases list showing restricted cases to non-participants**

Commit `42699ebc` ("refactor(database): flatten the restricted case filter", 2025-09-02) removed an `and_` in `restricted_case_filter` (`src/dispatch/database/service.py`). Without it, every restricted case matched for non-admin users. I restored the grouping. The existing `test_restricted_case_filter_with_test_data` fails without the fix and passes with it. I did not trace the HTTP endpoint end-to-end.

**3. Entity extraction returning only the first match**

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", 2025-09-02) added `[:1]` to the JSONPath call. I restored the full match list. `tests/entity/test_entity_service.py::test_find_entities_with_field_only` fails with the bug and passes with the fix. The date does not match "this week", so check whether something else changed CI.

**4. Masked tokens grouping unrelated signal instances**

The masking step is `redact_raw` in `src/dispatch/signal/redaction.py`, called from `signal_instance_create_flow`. The mask value `"[REDACTED]"` is a string that the entity JSONPath still matched, so every masked token became the same entity, and the deduplication filter grouped those instances. Two other callers, `entity_type/service.py` and `entity_type/flows.py`, read the raw payload without masking. I changed `find_entities` to extract from `redact_raw(...)` and skip the mask value. The masking itself is unchanged. The new tests are in `tests/entity/test_entity_masking.py`, and both fail before the fix and pass after. The entity, signal and entity_type suites pass (51 passed, 1 skipped).

**Other findings**

- Signal instances are written unmasked to the database by the POST handler. Masking runs later, in the processing loop.
- `entity_type/flows.py:29` assigns the result of `list.append`, which is `None`. The recalculation does nothing. I did not change it.
- Environment: `python -m pytest` fails here with `No module named 'slack_sdk'`. I installed `slack_sdk` into the venv, but the failure persists under `python -m pytest`. I ran the suites through `pytest.main` with `python -I`. The full test suite was not run.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4