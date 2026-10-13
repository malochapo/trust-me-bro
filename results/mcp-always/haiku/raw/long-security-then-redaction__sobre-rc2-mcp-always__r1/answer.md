Recap for the weekly report. Nothing is committed; all changes are in the working tree.

**1. Write routes without a permission check (case and incident APIs)**
- Five write routes had no `PermissionsDependency` on their route definition: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`, and `delete_custom_event`. I checked the route decorators only, not the parent `authenticated_organization_api_router` in `src/dispatch/api.py`, so a router-level check could still cover them.
- `create_case` and `create_incident` are the open report routes, which is intentional.
- `create_case_channel` and `create_case_resources` never had a check, per `git blame`. They are an open design question, and I left them unchanged.
- `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, 2025-07-14) removed its `IncidentEventPermission` check, and the message gives no reason. I restored the check in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views.py`. The test fails without the check. It inspects the declared dependencies, so it would not catch a check that is declared and then bypassed in the handler.

**2. Restricted cases visible to non-participants**
- The cause was `restricted_case_filter` in `src/dispatch/database/service.py`. Commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02) removed the `and_` that required a participant match for restricted cases. Any restricted case then passed for any non-admin user.
- I restored the grouping. `python -m pytest tests/database tests/case` gives 40 passed. The existing `test_restricted_case_filter_with_test_data` fails on the old code. I did not test the endpoint end to end as a member account.

**3. Masking of signal raw payloads**
- Masking is `redact_raw` in `src/dispatch/signal/redaction.py`, introduced in `d2675cf4` ("feat(signal): mask sensitive raw fields before processing", Sam Ortega, 2025-07-03). It runs in `signal_instance_create_flow` before entity extraction and filtering.
- Default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`. Matching is exact on the key name, case-insensitive.
- The unmasked payload is written to the database by the POST route, and stays there until the background poller processes the instance. After processing, the masked version is what gets committed. The POST response also returns the unmasked payload, which is the caller's own input.

**4. Entity extraction and the grouped "Personal access token exposed" instances**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02) added `[:1]` to the JSONPath matches. Only the first match became an entity. I removed the slice. `tests/entity` went from 1 failed to 11 passed.
- A separate bug: `find_entities` extracted from the raw payload without masking it, so a masked token became an entity with the value `"[REDACTED]"`. Every instance then shared that entity, and the deduplication filter grouped them. The masking was done only in the signal flow, but other callers read the stored, still unmasked payload.
- Fix in `src/dispatch/entity/service.py`: extraction now runs on `redact_raw(signal_instance.raw)`, and matches equal to `"[REDACTED]"` are skipped. Masking is unchanged. I added `tests/entity/test_entity_redaction.py` (two tests). The first failed before the fix. `python -m pytest tests/entity tests/signal` gives 45 passed, 1 skipped.
- Limit: the skip is by value. A real field whose value is literally `"[REDACTED]"` is also skipped. I did not run the GitHub signal end to end through deduplication.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4