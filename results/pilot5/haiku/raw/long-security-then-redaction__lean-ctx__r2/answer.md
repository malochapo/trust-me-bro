Here is the recap for the weekly report. Nothing is committed; all changes are in the working tree.

**1. Unprotected write routes (review question)**
Five data-changing routes in `case/views.py` and `incident/views.py` had no `PermissionsDependency`. Four are open on purpose (reporting a case or an incident). One was a regression: `incident.delete_custom_event` lost its `IncidentEventPermission` check in `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, 2025-07-14). I restored the check, and `tests/incident/test_incident_event_permissions.py` fails if it is removed again. The test was verified to fail without the check.

**2. Restricted cases visible to non-participants (security team report)**
`restricted_case_filter` in `database/service.py` had lost the `and_(...)` around the restricted-visibility and participant-email conditions. Members therefore passed the filter for every restricted case. `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02) introduced it. I restored the wrapper, matching the incident filter. `test_restricted_case_filter_with_test_data` went from `4 == 3` to passing, with no existing tests changed.

**3. Signal instance flow and masking (architecture question)**
- `POST /api/v1/{organization}/signals/instances` (`signal/views.py:70`) only stores the instance (`signal/service.py:create_instance`, lines 650–723). It does not redact, extract entities, filter or open a case.
- The `dispatch signals process` loop (`cli.py:937`) later picks up unfiltered instances with no case and runs `signal_instance_create_flow` (`signal/flows.py:46`). That flow masks `raw`, extracts entities, filters duplicates and snoozes, then creates the case if the signal allows it.
- Masking is `redact_raw` in `signal/redaction.py:10`, introduced in `d2675cf4` ("feat(signal): mask sensitive raw fields before processing", Sam Ortega, 2025-07-03). Default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`. Matching is exact on the lowercased key, at any depth.
- The unmasked payload is written to the database by the API commit (`signal/views.py:120`). It is overwritten with the masked version once processing succeeds. Instances whose processing keeps failing keep the unmasked payload.

**4. Entity extraction returned only the first match**
`beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02) added `[:1]` to the JSONPath lookup in `find_entities`. I removed the slice. `tests/entity` is green again.

**5. Masked values becoming entities (follow-up)**
Entities were extracted from the masked copy. A JSONPath that matched a masked field produced the placeholder `"[REDACTED]"` as an entity value, so unrelated instances shared one entity and were grouped by the dedup filter. `find_entities` now masks the payload itself and ignores any match equal to the placeholder. I added `tests/entity/test_entity_masking.py`, which fails without the fix and passes with it.

**Test status:** `tests/entity`, `tests/signal`, `tests/database`, `tests/case`, `tests/incident` and `tests/entity_type` pass (91 passed, 1 skipped). The full suite has 6 failures in `tests/ai/test_ai_service.py`. They come from the sandbox being unable to download a tokenizer file, not from these changes.

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

Two notes for the write-up. `UNPROTECTED_AT_START` lists five handlers, including `incident.create_incident`, which is intentionally open; the first answer's "four" count was wrong and has been corrected. `UNMASKED_IN_DATABASE` comes from reading the code, not from a live run.