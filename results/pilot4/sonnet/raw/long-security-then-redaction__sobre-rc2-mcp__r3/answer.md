## Recap

### Investigation 1: signal instance flow and masking
`POST /api/v1/{organization}/signals/instances` does not process the instance in the request.
- **Request.** The handler resolves the project and the signal definition, calls `create_instance` and commits. A scheduler loop later picks up instances where `filter_action` and `case_id` are both null.
- **Flow.** `signal_instance_create_flow` masks the payload, extracts entities, then applies the snooze and dedup filters. A filtered instance stops there. Otherwise it is stored without a case if it is a canary or `create_case` is off, or it opens a case.
- **Masking.** `redact_raw` replaces the value of any key in the field list with `"[REDACTED]"`. Matching is case-insensitive, on key names only, at any depth. The masking was introduced by `d2675cf4`.
- **Defaults.** The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- **Unmasked data in the database.** The request handler commits the original payload before the scheduler masks it. The scheduler path stores it unmasked too, and an instance that is never processed stays unmasked. The `POST` response also returns the unmasked payload.

### Investigation 2: what broke this week
- **Missing permission check.** In the case and incident views, five handlers changed data without a `PermissionsDependency`:
  - `create_case` and `create_incident` are open on purpose, because anyone may report a case or an incident.
  - `create_case_channel` and `create_case_resources` have never had a check. I flagged them as a possible design gap and left them as they are.
  - `delete_custom_event` is the regression. Commit `28c21e1e` ("tidy custom event routes") dropped its `IncidentEventPermission`. I restored it and added `tests/incident/test_incident_views.py`.
- **Restricted cases visible to non-participants.** Commit `42699ebc` flattened `restricted_case_filter` and removed the `and_`, so every restricted case matched. I restored the grouping.
- **Entity extraction keeping only the first match.** Commit `beb60cc4` sliced the JSONPath results to `[:1]`. I removed the slice.
- **Dedup grouping unrelated instances.** The masked `"[REDACTED]"` value was becoming an entity, so unrelated instances shared one entity. `find_entities` now skips masked values, and I added a test for it.

Nothing is committed. Existing tests were not changed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4