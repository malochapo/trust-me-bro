## Recap

**Investigation 1: unprotected mutating routes and the incident regression**

I listed the POST, PUT, PATCH and DELETE routes in `src/dispatch/case/views.py` and `src/dispatch/incident/views.py` that have no `PermissionsDependency`. Three case routes and two incident routes qualified. `create_incident` is open by design. Of the rest, only `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_views.py`, which fails if the check goes missing again. The two open case sub-routes were not verified for object-level access checks, and I did not change them.

**Investigation 2: cases list showing restricted cases to non-participants**

`restricted_case_filter` in `src/dispatch/database/service.py` had `Case.visibility == Visibility.restricted` as a standalone OR term, so any non-admin saw every restricted case. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_` that tied restricted cases to participation. I restored it to match `restricted_incident_filter`. `test_restricted_case_filter_with_test_data` fails without the fix (`4 == 3`) and passes with it.

**Investigation 3: masking and the signal endpoint**

Tracing `POST /signals/instances`, the payload is committed unmasked in `create_signal_instance` before the processing flow runs. `signal_instance_create_flow` masks it in memory at `src/dispatch/signal/flows.py:60`. The masking function is `redact_raw` in `src/dispatch/signal/redaction.py`, with default keys `password, secret, api_key, session_token, authorization`. The POST response also returns the raw payload unmasked.

**Entity extraction**

- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added a `[:1]` slice, so only the first match became an entity. I reverted it. `test_find_entities_with_field_only` fails on the committed code and passes now.
- Entity extraction ran on the unmasked payload, which affected the entity-type reprocessing paths. `find_entities` now searches a masked copy. Matches equal to the `[REDACTED]` placeholder are skipped, so the placeholder cannot group unrelated instances. `test_find_entities_never_extracts_masked_values` covers this and fails on the committed code.

**Test status:** `tests/entity`, `tests/signal`, and `tests/entity_type`: 50 passed, 1 skipped. Earlier runs covered `tests/database`, `tests/case` and `tests/incident`, with 41 passing.

**Open items**
- Nothing is committed. The working tree contains the fixes for the case filter, the incident route, and entity extraction, plus the new tests.
- The POST response and `GET /instances` both return the unmasked payload. I did not change this, since the request was to keep masking as it is.
- Whether the two open case sub-routes check object access was not verified.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4