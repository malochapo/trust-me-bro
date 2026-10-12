Here is the recap for the weekly report. Nothing is committed.

**Investigation 1: the case and incident APIs**
- Five data-changing handlers had no `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, since anyone may report.
- `delete_custom_event` was a regression. Commit `28c21e1e` removed its `IncidentEventPermission` check.
  - I restored it in `src/dispatch/incident/views.py`.
  - I added `tests/incident/test_incident_views.py`, which fails if the check goes missing.
- `create_case_channel` and `create_case_resources` were never protected, from `ced74f33` and `f08a22b3`. I left them alone, but they are worth a second look.

**Investigation 2: restricted cases in the list**
- Commit `42699ebc` flattened `restricted_case_filter` so that every restricted case matched for every user. I restored the `and_(restricted, participant email)` condition in `src/dispatch/database/service.py`.
- `tests/database` and `tests/case` pass (40 tests). I added no test for this one.

**Investigation 3: signal instance flow and masking**
- The API stores the instance, including its raw payload, unmasked. The background flow `signal_instance_create_flow` masks it later, through `redact_raw`.
- The masking was introduced in `d2675cf4`.
- The unmasked payload does reach the database. It stays there until the consumer processes the instance, and for longer if processing fails and is retried.

**Investigation 4: entity extraction**
- Commit `beb60cc4` made `find_entities` keep only the first JSONPath match. I reverted that line and `tests/entity` passes (11 tests).

**Investigation 5: grouped "GitHub: Personal access token exposed" instances**
- The masked value `[REDACTED]` became an entity, so the dedup filter saw the same value on every instance. `find_entities` now skips masked values.
- I added `tests/entity/test_entity_redaction.py`, which fails without the fix.
- `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).
- Re-extraction on instances that haven't been masked yet could still turn a real secret into an entity. Masking before the first write would close that.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4