## Recap

All changes below are uncommitted in the working tree.

### 1. Permission review (`case/views.py`, `incident/views.py`)

Five mutating routes had no `PermissionsDependency`:
- **Intentional:** `create_case` and `create_incident`, because anyone may report one.
- **Regression:** `incident.delete_custom_event` (DELETE `/{incident_id}/event/{event_uuid}`).
  - Commit `28c21e1e` removed its `IncidentEventPermission` check.
  - I restored the check and added `tests/incident/test_incident_event_permissions.py`. The test covers all four incident event routes and fails without the fix.
- **Open question:** `case.create_case_channel` and `case.create_case_resources` have never had a check, as far as I could tell. I left them unchanged, and they still need a decision from you.

### 2. Restricted cases visible to non-participants

- **Cause:** commit `42699ebc` flattened the `and_` in `restricted_case_filter` (`database/service.py`). Every restricted case then matched for every non-admin user.
- **Fix:** I restored the `and_`. Existing tests are unchanged and 44 pass.
- **Not done:** I did not add a regression test for this one.

### 3. Signal instance flow and masking

- **Flow:** the API stores the instance and commits it. A background loop later redacts `raw`, extracts entities and applies filters. It then either creates a case or returns early.
- **Masking:** `redact_raw` in `signal/redaction.py` masks keys case-insensitively at any depth. It was introduced in commit `d2675cf4`.
- **Unmasked storage:** the view commits `raw` unmasked, and `update_instance` also writes it unmasked. So the unmasked payload does reach the database.
- **Fix not made:** I suggested redacting in `create_instance` and `update_instance`, but did not change either.

### 4. Entity extraction

- **Only the first match was kept:** commit `beb60cc4` added `[:1]` to `jpath.find(...)`. I reverted it, and `tests/entity` passes.
- **Unrelated instances grouped into one case:** `[REDACTED]` values were becoming a shared entity, and dedup grouped on it. `find_entities` now redacts the payload first and skips masked values.
- **Test:** I added `test_find_entities_never_extracts_masked_values`. It fails without the fix, and `tests/entity` plus `tests/signal` give 44 passed, 1 skipped.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95