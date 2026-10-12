## Recap

**Security review (case and incident write routes)**

Before my changes, five handlers changed data without a `PermissionsDependency`:
- `case.create_case` (open by design: anyone may report a case)
- `case.create_case_channel` and `case.create_case_resources` (never protected, so not a regression; whether they should be is still open)
- `incident.create_incident` (open by design: anyone may report an incident)
- `incident.delete_custom_event`: a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its permission check.

I restored `IncidentEventPermission` on `delete_custom_event` and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again.

**Restricted cases shown to non-participants**

`restricted_case_filter` in `src/dispatch/database/service.py` let every non-admin see every restricted case. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed an `and_()` that tied restricted visibility to a participant match. I restored it. `test_restricted_case_filter_with_test_data` fails without the fix and passes with it. No existing tests changed.

**Signal instance trace (no code changed)**

`POST /api/v1/{organization}/signals/instances` stores the raw payload unmasked. Masking happens later, in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`), when a worker processes the row. The redaction function, `redact_raw`, masks keys case-insensitively at any depth, using the default keys from `SIGNAL_REDACTED_RAW_FIELDS`. The unmasked payload is written to the database at ingest and stays there until the worker runs.

**Entity extraction first-match bug**

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath match in `find_entities`. I reverted it. `tests/entity` passes.

**Masked values becoming entities**

The signal flow masks `raw` before extraction, but a JSONPath aimed at a masked key still matched the `"[REDACTED]"` string. Every instance then shared that entity value, so the deduplication filter grouped unrelated instances into one case. `find_entities` now redacts the payload itself and skips masked values, so no caller can produce a masked entity. I added `tests/entity/test_entity_redaction.py`, which fails without the fix and passes with it. I did not trace which commit introduced this gap.

**Uncommitted:** all of the above. The changed files are `src/dispatch/database/service.py`, `src/dispatch/entity/service.py`, and `src/dispatch/incident/views.py`, plus the new test files under `tests/incident/` and `tests/entity/`.

**Open:** whether `case.create_case_channel` and `case.create_case_resources` should get a `PermissionsDependency`.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4