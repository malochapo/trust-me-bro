## Weekly recap

**1. Mutating routes missing a permission check (case and incident APIs)**

Before my changes, five mutating handlers had no `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`, and `delete_custom_event`. I checked this by parsing the route decorators in both view files.

- `create_case` and `create_incident` are open by design, since anyone may report a case or incident.
- `create_case_channel` and `create_case_resources` never had a check, so they are not regressions. Whether they should have one is still open.
- `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored it in `src/dispatch/incident/views.py`. A new test, `tests/incident/test_incident_event_views.py`, fails if the check goes missing again. It fails without the fix and passes with it.

**2. Cases list showing restricted cases to non-participants**

The cause was an unconditional `Case.visibility == Visibility.restricted` branch in `restricted_case_filter` (`src/dispatch/database/service.py`). That branch let any user see any restricted case. Commit `b05613b5` (#6155, "sec(authz)") introduced it. The fix requires a participant email match, the same as the incident filter. `tests/database/test_service.py` already covers this case: it fails without the fix and passes with it. The tests I ran pass (40 across `tests/database/test_service.py` and `tests/case`).

**3. Signal instance flow and masking**

- A POST to `/signals/instances` stores the raw payload unmasked and returns it unmasked. Masking happens later, in `signal_instance_create_flow` (`src/dispatch/signal/flows.py`), which a background loop runs. Until that flow runs, the unmasked payload is in the database.
- Masking is `redact_raw` in `src/dispatch/signal/redaction.py`. It matches keys case-insensitively at any depth, replacing matching values with `[REDACTED]`. The default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`.
- The masking was introduced by commit `d2675cf4` ("feat(signal): mask sensitive raw fields before processing").

**4. Entity extraction keeping only the first match**

Commit `beb60cc4` added `[:1]` to the JSONPath matches in `find_entities`. I removed the slice, and `tests/entity` passes.

**5. Masked values becoming entities (grouping bug)**

`find_entities` matched JSONPath against the unmasked payload, and the masked value `[REDACTED]` could itself become an entity. Its value was identical across instances, so the dedup filter grouped them. The fix is in `find_entities` (`src/dispatch/entity/service.py`):

- It matches against `redact_raw(signal_instance.raw)`.
- It skips any match equal to the mask.

I put this inside `find_entities` because other callers, such as the entity-type recalculation path, read stored payloads that can still be unmasked. A side effect: a real field whose value is exactly `[REDACTED]` will no longer become an entity. The new test is `tests/entity/test_entity_redaction.py`, and it fails without the fix. I reproduced the `[REDACTED]` entity but not the full analyst scenario with grouping.

**State of the work:** nothing is committed. The changes are in `src/dispatch/database/service.py`, `src/dispatch/entity/service.py`, and `src/dispatch/incident/views.py`, plus the new test files under `tests/entity/` and `tests/incident/`. I ran the affected test directories only, not the full suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: b05613b5
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4