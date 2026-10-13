Here is the recap for the weekly report. Nothing is committed, so the changes below are uncommitted working-tree edits.

**1. Permission review and the `delete_custom_event` regression**

I listed the POST/PUT/PATCH/DELETE routes in `src/dispatch/case/views.py` and `src/dispatch/incident/views.py` that have no `PermissionsDependency`. There are five: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`, and `delete_custom_event`. `create_case` and `create_incident` are open on purpose, since anyone may report a case or incident. `delete_custom_event` is a regression: commit `28c21e1e` ("refactor(incident): tidy custom event routes", Jul 14 2025) removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_views_permissions.py`, which fails if the check goes missing again. I did not change `create_case_channel` or `create_case_resources`. They were left unguarded by `ced74f33` and `f08a22b3`, and whether they need a check is still open.

**2. Cases list showing restricted cases to non-participants**

The member-role filter in `restricted_case_filter` (`src/dispatch/database/service.py`) had lost the pairing between "restricted" and "the user is a participant." Commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sep 2 2025) caused this. I restored that pairing. The database service tests pass, including `test_restricted_case_filter_with_test_data`, which had been failing with 4 results instead of 3.

**3. Signal instance flow (read-only trace)**

Masking happens in `redact_raw` (`src/dispatch/signal/redaction.py`), called from `signal_instance_create_flow`. It was introduced by `d2675cf4` (Jul 3 2025). The default keys are `password`, `secret`, `api_key`, `session_token`, and `authorization`. The unmasked payload is written to the database when the request commits, before processing masks it. Processing then overwrites it, but a failed run rolls back and leaves the payload unmasked.

**4. Entity extraction keeping only the first match**

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sep 2 2025) added `[:1]` to the JSONPath match in `find_entities`, which dropped every match after the first. I reverted that line, and `tests/entity` passes.

**5. Masked values becoming entities**

A "GitHub: Personal access token exposed" entity type matched the masked `session_token`. The flow had already replaced the value with `"[REDACTED]"`, so every instance produced the same entity, and the dedup filter grouped them into one case. `find_entities` now matches against a masked copy of the payload and skips any `[REDACTED]` value. This also covers the `entity_type` callers, which run before processing. The new `tests/entity/test_entity_redaction.py` fails without the fix and passes with it.

**Test status:** the full suite has 366 passed, 4 skipped, and 6 failed. The 6 failures are in `tests/ai/test_ai_service.py`. They also fail on the untouched tree, because the tokenizer download needs network access.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4