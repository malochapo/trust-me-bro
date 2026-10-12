## Recap

### Investigation 1: case and incident API permissions, and restricted cases

- **Unprotected routes at the start:** five routes changed data without a `PermissionsDependency`. I re-derived the list from `HEAD` just now. They were `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident` and `incident.delete_custom_event`.
- **Open on purpose:** `create_case` and `create_incident`, because anyone may report.
- **Not regressions:** `create_case_channel` and `create_case_resources` never had checks. They were added without them in `f08a22b3` and `ced74f33`. I left them unchanged.
- **Regression:** `delete_custom_event` lost its `IncidentEventPermission` check in `28c21e1e`. I restored it. I added `tests/incident/test_incident_view_permissions.py`, which fails if the check goes missing again.
- **Restricted cases visible to non-participants:** commit `42699ebc` flattened the `and_` in `restricted_case_filter` (`src/dispatch/database/service.py`). Every non-admin could then see every restricted case. I restored the `and_(restricted, participant email)` branch. I added no test for this one.

### Investigation 2: signal instance flow, masking and entity extraction

- **Flow of `POST /signals/instances`:** the view stores the instance and commits. The processing loop later runs `signal_instance_create_flow`. It masks `raw`, extracts entities, then applies snooze and dedup filters. If the instance is not filtered, it creates a case.
- **Masking:** `dispatch.signal.redaction.redact_raw` is called from `signal_instance_create_flow`. It masks matching keys case-insensitively, at any depth. The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- **Unmasked payload in the database:** yes. The view commits the raw payload before the flow masks it. If the worker is down or failing, it stays unmasked. I recommended masking in `create_instance`, but I have not made that change.
- **Entity extraction bug:** `beb60cc4` added `[:1]` to the JSONPath matches in `find_entities`, so only the first match became an entity. I reverted that, and `tests/entity` passes.
- **Grouped unrelated instances:** the masked value `[REDACTED]` was becoming one shared entity, so the dedup filter grouped everything. `find_entities` now skips masked values, and I added `tests/entity/test_entity_masked_values.py`. It fails without the fix.

Nothing is committed. I ran `tests/entity`, `tests/signal`, `tests/database`, `tests/case` and `tests/incident` along the way, but not the full suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95