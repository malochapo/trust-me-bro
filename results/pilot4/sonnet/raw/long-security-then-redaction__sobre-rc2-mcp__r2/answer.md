## Recap

**Investigation 1: permissions and visibility**
- Before my changes, five data-changing handlers had no `PermissionsDependency`. I re-derived this list from `HEAD` just now, since my earlier list was lost when the conversation was compacted. The five are `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, since anyone may report. `create_case_channel` and `create_case_resources` have never had a check, so they are a design gap worth a separate review.
- `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_route_permissions.py`, which fails if the check goes missing.
- Restricted cases appeared in the cases list because commit `42699ebc` flattened `restricted_case_filter` into three separate `or_` branches, so every restricted case matched for every user. I restored the `and_` wrapper.

**Investigation 2: signal pipeline**
- A signal instance is stored by the POST handler, then picked up by a worker. `signal_instance_create_flow` masks the payload with `redact_raw`, extracts entities, applies filters, and either opens a case or stops.
- The default masked keys are `password`, `secret`, `api_key`, `session_token` and `authorization`. Matching is by exact key name, case-insensitive, at any depth.
- The POST handler stores and commits the raw payload before masking, so the unmasked payload is written to the database.
- Commit `beb60cc4` made entity extraction keep only the first JSONPath match, and I reverted it.
- Masked values were becoming a shared `[REDACTED]` entity, so deduplication grouped unrelated instances into one case. `find_entities` now skips masked values, and `test_find_entities_skips_masked_values` covers it.

Nothing is committed. Seven tests in `tests/ai` and `tests/entity` were failing before my changes. The `tests/entity` one is fixed; the six in `tests/ai/test_ai_service.py` were not investigated, and I haven't re-run the full suite since.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4