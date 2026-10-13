## Weekly recap

**Write-endpoint permission review**
- Five write handlers had no `PermissionsDependency` before my changes. Three are in `case/views.py` and two in `incident/views.py`.
- `case.create_case` and `incident.create_incident` are open on purpose, since anyone may report a case or incident.
- `case.create_case_channel` and `case.create_case_resources` have never had a check. They look like design gaps, not regressions, so I left them unchanged for a decision.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` ("tidy custom event routes") removed its `IncidentEventPermission` check. I restored it, and `tests/incident/test_incident_event_views.py` fails if the check goes missing again.

**Restricted case visibility leak**
- Members could see restricted cases they did not participate in. The cause was `restricted_case_filter` in `src/dispatch/database/service.py`. Commit `42699ebc` ("flatten the restricted case filter") split the `and_` condition into separate clauses, which dropped the participant check. I restored the combined condition.
- `tests/database/test_service.py::test_restricted_case_filter_with_test_data` now passes, and the test is unchanged.

**Signal instance masking trace**
- Masking happens in `redact_raw` in `src/dispatch/signal/redaction.py`. It is called from `signal_instance_create_flow` in `src/dispatch/signal/flows.py`, and it was introduced in commit `d2675cf4`.
- Default masked keys: `password`, `secret`, `api_key`, `session_token`, `authorization`. Keys can be overridden with `SIGNAL_REDACTED_RAW_FIELDS`.
- The unmasked payload is written to the database. The POST handler commits the raw payload before the masking flow runs, and the response returns it unmasked. Masking only happens later in the processing flow.
- Still open, as you asked for a trace only: the unmasked payload is persisted, and the payload is returned unmasked in the POST response. Masking matches exact key names only, and there are no tests for `redact_raw`.

**Signal grouping by masked entity (PAT signal)**
- Masked values were turned into entities. `redact_raw` replaces a secret with `"[REDACTED]"`, and the entity JSONPath still matched that placeholder. Every instance then shared one `[REDACTED]` entity, and the deduplication filter grouped them into one case.
- Fix in `find_entities` (`src/dispatch/entity/service.py`): matching runs on a redacted copy of the payload, and any match equal to the mask is skipped. Masking itself is unchanged.
- New tests in `tests/entity/test_entity_redaction.py` cover masked and unmasked values.

**Entity extraction keeps only the first match**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added a `[:1]` slice to the JSONPath results. I removed the slice, so every match is extracted again.
- `tests/entity` passes (11 of 11).

**Test status:** the full suite gives 364 passed, 6 failed, 4 skipped. The 6 failures are in `tests/ai/test_ai_service.py`. They need a `tiktoken` encoding download, which fails because the sandbox has no network access. They are an environment issue, not a regression from these changes, but I have not confirmed that on a networked machine.

All changes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4