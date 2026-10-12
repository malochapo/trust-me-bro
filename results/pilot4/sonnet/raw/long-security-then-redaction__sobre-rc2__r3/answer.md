## Recap

**1. Permission review (case and incident APIs)**
- Before my changes, five data-changing handlers had no `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, because anyone may report a case or an incident.
- `delete_custom_event` was a regression. Commit `28c21e1e` removed its `IncidentEventPermission` check. I restored it in `src/dispatch/incident/views.py`. The new test `tests/incident/test_incident_event_permissions.py` fails if the check goes missing again.
- `create_case_channel` and `create_case_resources` look like an original gap, not a regression. I left them unchanged. Whether they should require `CaseEditPermission` is your design call.
- I did not check whether a router-level or `api.py` dependency covers any of these routes.

**2. Restricted cases visible to members**
- `restricted_case_filter` in `src/dispatch/database/service.py` had been flattened to `open OR restricted OR participant-email == me`. The bare `restricted` term matched every restricted case.
- Commit `42699ebc` introduced it. I restored `open OR (restricted AND participant-email == me)`.
- `tests/database` and `tests/case` pass. I added no new test for this.

**3. Signal instance trace and masking**
- The `POST` handler stores the instance and commits it with the full `raw` payload. A separate worker later runs `signal_instance_create_flow`, which masks the payload, extracts entities, then applies snooze and dedup filters. It either links the instance to an existing case or creates a new one.
- Masking is done by `redact_raw` in `dispatch.signal.redaction`. It masks by key name, case-insensitively, at any depth. The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- The unmasked payload is written to the database, because the view commits before the worker masks it. `update_instance` also writes unmasked data. The masking was introduced in commit `d2675cf4`.

**4. Entity extraction bugs**
- Commit `beb60cc4` made `find_entities` keep only the first JSONPath match. I removed the `[:1]` slice and `tests/entity` went green.
- Masked values were becoming entities with the value `[REDACTED]`, so unrelated instances were deduplicated into one case. `find_entities` now skips values equal to the mask. I added `test_find_entities_ignores_masked_values`.
- All changes are uncommitted. I did not run the whole test suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4