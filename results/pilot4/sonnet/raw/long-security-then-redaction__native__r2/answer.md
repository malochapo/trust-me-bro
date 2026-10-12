Over the day I looked at four things: unprotected mutating routes, a restricted-case visibility leak, how signal payloads are masked, and an entity extraction regression. The last of those also produced a second, related bug.

## Review of the case and incident APIs
- Five data-changing routes in `case/views.py` and `incident/views.py` declared no `PermissionsDependency`.
- `create_case` and `create_incident` are open on purpose, since anyone may report a case or an incident.
- `create_case_channel` and `create_case_resources` never had a check. That is a design gap, not a regression.
- `delete_custom_event` (incident) is a regression. Commit `28c21e1e` removed its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again.

## Restricted cases shown to non-participants
- `restricted_case_filter` in `database/service.py` had its `and_(restricted, participant email == user)` flattened into separate `or_` branches. Every restricted case therefore matched for non-admin users.
- Commit `42699ebc` introduced it. I restored the `and_` grouping and changed no tests.
- No test covers this filter, so none would catch it coming back.

## Signal instance flow and masking
- `POST /signals/instances` stores the payload as received and commits it. The scheduler processes it later through `signal_instance_create_flow`, which masks the payload before entity extraction.
- Masking is done by `redact_raw` in `dispatch.signal.redaction`. It replaces values of the keys `password, secret, api_key, session_token, authorization` with `[REDACTED]`, case-insensitively and at any depth.
- Because the API commits before masking runs, the unmasked payload is written to the database. It stays there until the scheduler processes the instance, and permanently if processing never happens or fails.
- Commit `d2675cf4` added the masking.

## Entity extraction
- Commit `beb60cc4` added `[:1]` to the JSONPath lookup, so only the first match became an entity. I reverted that line, and `tests/entity` passes.
- Masked values then became entities. Every instance of "GitHub: Personal access token exposed" produced the same `[REDACTED]` entity, which made the dedup filter group unrelated instances into one case.
- `find_entities` now skips masked values. I added `tests/entity/test_entity_redaction.py`, which fails without the fix.

All changes are uncommitted in the working tree. I did not run the full test suite, only the directories relevant to each fix.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4