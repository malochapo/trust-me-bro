## Recap

**1. Unguarded write routes and the deleted permission check (incident and case APIs)**

- Five state-changing handlers had no `PermissionsDependency` at HEAD: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, since anyone may report a case or incident.
- `delete_custom_event` is a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes", Jul 14 2025) dropped its `IncidentEventPermission` check. I restored the check in `src/dispatch/incident/views.py`.
- I added `tests/incident/test_views.py`, which asserts that the DELETE route keeps `IncidentEventPermission`. It passes with the fix and fails without it.
- `create_case_channel` and `create_case_resources` have never been guarded (commits `ced74f33` and `f08a22b3`), so they are not regressions. Whether they need a check is still open.

**2. Cases list showing restricted cases to non-participants**

- `restricted_case_filter` in `src/dispatch/database/service.py` let any non-admin user see every restricted case. The participant check was applied only to the open branch.
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sep 2 2025) removed the `and_()` that required the participant match. The commit was labelled a refactor but changed behaviour.
- I restored the check to match the incident filter. The existing test `test_restricted_case_filter_with_test_data` fails without the fix and passes with it. 51 tests pass across the database, case, incident and case suites. No tests were changed.

**3. Signal instance flow: masking, leaks and entity extraction**

- Masking happens in `redact_raw` in `src/dispatch/signal/redaction.py`. The signal flow calls it before entity extraction. The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`, matched case-insensitively on exact key names at any depth. The masking was introduced in `d2675cf4`.
- The unmasked payload is written to the database. `POST /instances` commits the raw payload as sent, and the flow masks it later. The POST response also returns the unmasked payload. Until the processing loop runs, the unmasked payload is stored.
- Entity extraction read the raw payload, so the masked placeholder became an entity value. Every instance with that field got the same entity, and the deduplication filter grouped them into one case. I changed `find_entities` in `src/dispatch/entity/service.py` to search a masked copy and skip the placeholder value. Two new tests are in `tests/entity/test_entity_redaction.py`. They fail without the fix and pass with it. The signal, entity type and entity suites pass (51 passed, 1 skipped).
- Entity extraction also returned only the first JSONPath match, so the entity tests failed (CI red). That came from `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sep 2 2025). The change saved no work, so I removed the slice. The entity suite passes again.

**Open items**

- Nothing is committed. Changes are in `src/dispatch/database/service.py`, `src/dispatch/entity/service.py` and `src/dispatch/incident/views.py`, plus the untracked `tests/incident/` and `tests/entity/test_entity_redaction.py`.
- Decide whether the two case resource routes should get a permission check.
- Check how many existing cases were grouped by the placeholder entity. This change does not fix them.
- `src/dispatch/entity_type/flows.py` assigns `None` from `append`, so that flow does nothing. Not fixed.

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