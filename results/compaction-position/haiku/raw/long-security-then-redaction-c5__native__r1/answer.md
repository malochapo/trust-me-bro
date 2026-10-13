## Recap: authorization review and signal/entity fixes

**Authorization review (case and incident write routes)**
- Five write routes had no `PermissionsDependency` at HEAD: three in the case API and two in the incident API.
- `create_case` and `create_incident` are open on purpose, since anyone may report a case or incident.
- `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") dropped its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_event_views.py`, which fails if the check goes missing. Before the fix it failed with `assert IncidentEventPermission in []`.
- `create_case_channel` and `create_case_resources` are unprotected too, but I have not decided whether they are design choices or regressions. The origin of `create_case_resources` is untraced.

**Restricted case visibility**
- Members could see restricted cases they were not part of. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_` that required participation. The earlier security fix `b05613b5` (#6155) had the correct form. I restored it in `restricted_case_filter`, in `src/dispatch/database/service.py`. Its test suite passes, but I have not added a regression test for it.

**Signal instance masking**
- Masking happens in `signal_instance_create_flow`, through `redact_raw` in `src/dispatch/signal/redaction.py`. The masking was introduced by `d2675cf4`.
- Default masked keys are `password`, `secret`, `api_key`, `session_token`, and `authorization`. Matching is exact and case-insensitive, so keys such as `token` or `client_secret` are not masked.
- The unmasked payload is written to the database. The API commits the raw payload before the worker redacts it, and it stays unmasked if processing fails. **This gap is not fixed.** I suggested redacting before the first commit, and you have not asked for that yet.

**Entity extraction**
- Extraction kept only the first match because of `beb60cc4` ("perf(entity): stop at the first JSONPath match"). I reverted it, and `tests/entity` passes. I did not reproduce the red CI state before the fix.
- Masked values could also become entities. `find_entities` now redacts the payload before matching and skips the `[REDACTED]` placeholder. This closes the path behind "GitHub: Personal access token exposed" grouping unrelated instances. I added `test_find_entities_never_creates_entity_from_masked_value`, which failed before the fix. `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**Working tree:** all changes are uncommitted: `src/dispatch/database/service.py`, `src/dispatch/entity/service.py`, `src/dispatch/incident/views.py`, `tests/entity/test_entity_service.py`, and the new `tests/incident/`.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4