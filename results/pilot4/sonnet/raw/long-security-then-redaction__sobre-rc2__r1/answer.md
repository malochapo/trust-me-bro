## Recap

**1. Permission review (case and incident APIs)**
- Five data-changing routes had no `PermissionsDependency` when I started. The `create_case` and `create_incident` routes are open on purpose, because anyone may report. The two case resource routes (`create_case_channel` and `create_case_resources`) never had a check, so I reported them as an oversight and left them alone.
- The only regression was `incident.delete_custom_event`. Commit `28c21e1e` removed its `IncidentEventPermission`. I restored the check and added `tests/incident/test_incident_event_views.py`, which fails if the check goes missing.
- My first answer said "six in total", which was a miscount. The list was five routes.

**2. Restricted cases on the cases list**
- Commit `42699ebc` flattened `restricted_case_filter` in `src/dispatch/database/service.py` into one `or_`. That made every restricted case visible to non-privileged users.
- I restored the `and_` of "restricted and the user is a participant". The existing tests were not changed and pass. I did not add a regression test for this one.

**3. Signal instance flow and masking**
- Masking is done by `dispatch.signal.redaction.redact_raw`, called from `signal_instance_create_flow`. It was introduced by commit `d2675cf4`.
- It runs in the worker step, not in the API route. `POST /instances` commits the unmasked `raw` first, so the unmasked payload is written to the database until the worker processes the instance. The 200 response also carries the unmasked payload.
- The default masked keys are `password`, `secret`, `api_key`, `session_token` and `authorization`, matched exactly and case-insensitively.

**4. Entity extraction**
- Commit `beb60cc4` ("stop at the first JSONPath match") made `find_entities` keep only the first match. I reverted it, and `tests/entity` passes.

**5. Masked values grouped into one case**
- The masked token (`[REDACTED]`) became a shared entity, so the deduplication filter merged unrelated instances. `find_entities` now skips masked values. The masking itself is unchanged.
- I added `tests/entity/test_entity_masked_values.py`.

None of the changes are committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4