Here's the recap for the weekly report. Everything below is uncommitted in the working tree.

**1. Unprotected write routes (permissions review)**
Before my changes, five write handlers had no `PermissionsDependency`. Two are intentionally open: `create_case` and `create_incident`, since anyone may report a case or incident. `create_case_channel` and `create_case_resources` have never had a check. That is a design question I have not acted on. `delete_custom_event` in `incident/views.py` had lost its check in commit `28c21e1e` (2025-07-14), so it was a regression. I restored `IncidentEventPermission` on the route and added `tests/incident/test_incident_views_permissions.py`, which fails if the check is removed. The test passes with the fix and fails without it.

**2. Restricted cases visible to non-participants**
The cases list showed restricted cases to members who were not participants. `restricted_case_filter` in `database/service.py` had lost its `and_` grouping when commit `42699ebc` (2025-09-02) flattened the filter. I restored the grouping. `test_restricted_case_filter_with_test_data` fails on the buggy code and passes with the fix. No existing tests were changed.

**3. Entity extraction returned only the first match**
Commit `beb60cc4` (2025-09-02) added `[:1]` to the JSONPath match in `entity/service.py`, so multi-match paths produced one entity. I removed the slice. `tests/entity` went from 1 failed to 11 passed.

**4. Masked values becoming entities**
Masking runs only in `signal_instance_create_flow`. Other entity paths read the stored payload directly, so an unmasked token could become an entity, and the dedup filter then grouped unrelated instances on it. `find_entities` now matches against a redacted copy and skips `[REDACTED]` values. `redact_raw` is unchanged. The new test `tests/entity/test_entity_masking.py` fails without the guard. `tests/signal`, `tests/entity_type` and `tests/entity` pass: 50 passed, 1 skipped.

**Open items**
- I haven't verified what runs `main_processing_loop`. Nothing in the repo calls it.
- `entity_type/flows.py` has `entity_types = ....append(entity_type)`, which assigns `None`. The recalculation block for historical signals may never run. I noticed this but didn't change it.
- The full test suite has not been run.

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