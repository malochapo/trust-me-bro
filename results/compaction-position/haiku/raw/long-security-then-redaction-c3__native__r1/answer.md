Here is the recap for both investigations.

**1. Permission gaps on the case and incident APIs**

Before any changes, five mutating handlers had no `PermissionsDependency`:
- `case.create_case`, `case.create_case_channel`, `case.create_case_resources`
- `incident.create_incident`, `incident.delete_custom_event`

`create_incident` and `create_case` are open by design, since anyone may report one. `create_case_channel` and `create_case_resources` have never had a check, so they are a decision for the team, and I left them as they were.

`incident.delete_custom_event` was a regression. Commit `28c21e1e` removed its check. I restored `PermissionsDependency([IncidentEventPermission])` and added `tests/incident/test_incident_views_permissions.py`, which fails if the check is removed again.

**2. Restricted cases visible to non-participants**

`restricted_case_filter` in `src/dispatch/database/service.py` had lost the `and_` that limits restricted cases to participants. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") introduced the leak. I restored the grouping. `test_restricted_case_filter_with_test_data` was already failing and now passes. `tests/database`, `tests/case`, and `tests/incident` give 41 passed.

**3. Signal instance flow: masking and extraction**

- Masking happens in `signal_instance_create_flow`, through `redact_raw`. It is introduced by `d2675cf4`. The default keys are `password`, `secret`, `api_key`, `session_token`, and `authorization`.
- The unmasked payload is written to the database when the API commits the new instance, before processing masks it. That is a known window, and I did not change it.
- Entity extraction kept only the first JSONPath match because of `beb60cc4`. This broke `tests/entity`. I removed the `[:1]`, and the tests pass.
- Masked values were becoming entities whose value was `"[REDACTED]"`, which let unrelated instances dedup into one case. I fixed this in `find_entities`, which now searches the redacted payload and skips masked matches. It covers every caller, including the entity-type reprocessing paths. I added `tests/entity/test_entity_masking.py`. Those tests fail without the fix.

Nothing is committed. The changes are in `src/dispatch/database/service.py`, `src/dispatch/incident/views.py`, `src/dispatch/entity/service.py`, and the new test files under `tests/incident/` and `tests/entity/`.

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