## Recap

### 1. Case and incident permission review

At the start, five data-changing handlers had no `PermissionsDependency`:
- **Case:** `create_case`, `create_case_channel` and `create_case_resources`.
- **Incident:** `create_incident` and `delete_custom_event`.

`create_case` and `create_incident` are open on purpose, because anyone may report. `create_case_channel` and `create_case_resources` never had a check, so they are a gap, not a regression. I flagged them and left them unchanged.

`incident.delete_custom_event` was the one regression. Commit `28c21e1e` removed its `IncidentEventPermission`. I restored it and added `tests/incident/test_incident_views.py`, which fails if the check goes missing.

The restricted-case visibility leak was a second regression. Commit `42699ebc` ("flatten the restricted case filter") turned `or_(open, and_(restricted, participant))` into a flat `or_`. That made every restricted case visible to every non-admin user. I restored the `and_` in `restricted_case_filter` (`database/service.py`). Existing tests already passed with the bug, and I did not add a new test for it.

### 2. Signal instance flow

- **Ingest:** `POST /signals/instances` stores the instance and commits it. The raw payload is not masked at this point.
- **Processing:** a background loop later runs `signal_instance_create_flow`, which does four things in order:
  - masks the payload with `redact_raw` (`signal/redaction.py`);
  - extracts entities;
  - applies snooze and dedup filters, which is how an instance is filtered out;
  - creates a case, unless the instance is a canary or the signal has `create_case` off.
- **Masking:** keys match case-insensitively, at any depth, and exactly. The default keys are `password, secret, api_key, session_token, authorization`. The masking commit is `d2675cf4`.
- **Unmasked payload:** it is written to the database at ingest. It stays there until the processor commits the masked version, or permanently if processing fails.

### 3. Entity extraction bugs

- **First match only:** commit `beb60cc4` added `[:1]` to the JSONPath matches, so only the first match became an entity. I removed it, and `tests/entity` passes.
- **Grouped GitHub signals:** after masking, every instance had the same `[REDACTED]` string at the token path, so one shared entity linked unrelated instances. The dedup filter on that entity type then grouped them. `find_entities` now skips masked values, which covers every extraction path. I added `tests/entity/test_entity_masked_values.py`, which fails without the fix.
- **Not cleaned up:** entities and case links created before the fix are still in the database.

Nothing is committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb9
VISIBILITY_BUG: 42699ebc7c
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc494
MASKING_COMMIT: d2675cf4b0