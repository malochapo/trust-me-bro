## Weekly recap

**Route permission audit and regression fix (incident and case APIs)**
- Five mutating handlers had no `PermissionsDependency` before my changes. Creating a case (`create_case`), creating a case channel (`create_case_channel`), and adding case resources (`create_case_resources`) are open by design, and I left them alone. Creating an incident (`create_incident`) is also open by design. `delete_custom_event` was the regression.
- `delete_custom_event` had lost its `IncidentEventPermission` check in commit `28c21e1e` ("refactor(incident): tidy custom event routes"), which deleted one line. I restored the check.
- I added `tests/incident/test_incident_event_views.py`. It fails if the check goes missing again. It failed before the restore and passes after.
- Open question: `create_case_channel` and `create_case_resources` may need `CaseEditPermission`. I did not change them.

**Restricted case visibility leak (cases list)**
- The cause was `restricted_case_filter` in `src/dispatch/database/service.py`. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_` wrapper. As a result, any restricted case passed the filter whenever the member matched on the contact email. The sibling `restricted_incident_filter` still uses the correct pattern.
- I restored the `and_` wrapper. `tests/database/test_service.py` and the case selection tests pass (26 passed). The existing test `test_restricted_case_filter_with_test_data` fails on the original file and passes on the fix.

**Entity extraction keeping only the first match**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath lookup in `find_entities`. I removed the slice. `tests/entity` passes (11 passed on the fix alone).

**Masked values becoming entities (GitHub PAT signal)**
- Masking runs in `signal_instance_create_flow` before entity extraction. The JSONPath still matched the masked key, so every instance got the entity value `"[REDACTED]"`. The deduplication filter then grouped unrelated instances into one case.
- A second path re-extracts entities from the stored raw, which is unmasked, so it could turn the real token into an entity.
- Fix: `find_entities` now masks the payload itself and skips any match equal to the mask. The masking rules are unchanged. New tests are in `tests/entity/test_entity_masking.py`. They fail without the fix and pass with it. `tests/entity` and `tests/signal` give 45 passed, 1 skipped.
- Still open: regex-only entity types produce no entities in `find_entities`, and the raw payload is still stored unmasked at POST time.

**Signal masking trace (read-only)**
- Masking happens in `redact_raw` in `src/dispatch/signal/redaction.py`. It matches keys case-insensitively at any depth.
- Masking was introduced in commit `d2675cf4` ("feat(signal): mask sensitive raw fields before processing"), 2025-07-03.
- The raw payload is stored unmasked at POST, and `update_instance` also writes it unmasked, so the unmasked payload does reach the database.

No commits were made. All changes are in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4