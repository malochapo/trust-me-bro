## Recap

**Restricted cases visible to non-participants.** Members of the security team could see restricted cases they were not part of. The cause was commit `42699ebc`, which flattened `restricted_case_filter` in `src/dispatch/database/service.py`. It dropped the `and_` that requires participation for restricted cases, so every restricted case matched for non-admin roles. I restored the clause, matching the incident filter. The existing test `test_restricted_case_filter_with_test_data` fails without the fix and passes with it.

**Permission review.** The review first found no regression, and that was wrong. A later scan turned up `DELETE /incident/{incident_id}/event/{event_uuid}`, whose `IncidentEventPermission` check was removed by `28c21e1e` ("refactor(incident): tidy custom event routes", 2025-07-14). I restored the check. The new test `tests/incident/test_incident_event_permissions.py` fails without it. The earlier review had also missed `create_case` and `create_incident`, which are open by design. Still open: the two case resource routes (`create_case_channel`, `create_case_resources`) are unprotected, and which permission to add is undecided.

**Signal payload masking.** A signal instance's raw payload is masked by `redact_raw` in `src/dispatch/signal/redaction.py`, which runs in the signal flow before entity extraction. The default keys are listed below. The API commits the unmasked payload before processing, so the unmasked payload does reach the database until the flow overwrites it. Masking was introduced in `d2675cf4`.

**Entity extraction keeps only the first match.** Commit `beb60cc4` added `[:1]` to the JSONPath lookup, so only one value per entity type became an entity. I removed the slice, which fixes `test_find_entities_with_field_only`.

**Masked values becoming entities.** Every instance of the "GitHub: Personal access token exposed" signal produced the same entity, the literal `"[REDACTED]"`, so the deduplication filter grouped them into one case. `find_entities` now masks the payload itself and skips masked values. The new test `test_find_entities_never_extracts_masked_values` fails without the fix. Entities already stored with the value `"[REDACTED]"` are not cleaned up.

**Verification:** Full suite: 363 passed, 4 skipped, 6 failed. The 6 failures are in `tests/ai`, caused by tiktoken being unable to download its encoding (no network). They predate this work. Nothing is committed. Uncommitted changes: `src/dispatch/database/service.py`, `src/dispatch/entity/service.py`, `src/dispatch/incident/views.py`, `tests/entity/test_entity_service.py`, and the new `tests/incident/`.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4