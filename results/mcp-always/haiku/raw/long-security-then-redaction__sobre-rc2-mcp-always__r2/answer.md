Both investigations are done and nothing is committed. The changes sit in the working tree.

**1. Permission regression on custom event deletion**
- Four handlers in `case/views.py` and `incident/views.py` change data without a permission check. Two of them are `create_case_channel` and `create_case_resources` in `case/views.py`. They never had a check, so they are a design gap, not a regression, and I left them alone. The other is `incident.delete_custom_event`.
- `incident.delete_custom_event` lost its `IncidentEventPermission` check in `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored it. A new test, `tests/incident/test_incident_event_permissions.py`, fails without the check and passes with it.
- `POST /{incident_id}/...` at `incident/views.py:163` is guarded only by `IncidentViewPermission`, so a write goes through a view-level check. I reported it and did not change it.

**2. Members seeing restricted cases they are not part of**
- Cause: `restricted_case_filter` in `database/service.py` lost its participant check. Restricted cases matched for every non-admin user.
- Introduced by `42699ebc` ("refactor(database): flatten the restricted case filter"), which was labelled a refactor but changed behavior. The filter itself came from `b05613b5`.
- Fix: restored the participant `and_` clause, matching `restricted_incident_filter`. `tests/database/test_service.py` and `tests/case` pass (40 passed). I did not run the HTTP list endpoint.

**3. Entity extraction keeping only the first match**
- Commit `beb60cc4` added `[:1]` to the JSONPath match list, so only the first match became an entity. I reverted that line. `tests/entity` passes (11 passed).

**4. Masked values becoming entities**
- Cause: the flow masks `raw` in memory before entity extraction. A JSONPath that points at a masked key reads `"[REDACTED]"`, so every instance got the same entity. The deduplication filter then grouped them.
- Fix: `_find_entities_by_jsonpath_expression` in `entity/service.py` skips values equal to `MASK`. The masking is unchanged. The new test file `tests/entity/test_entity_redaction.py` has two tests, and both fail without the guard. `tests/entity` and `tests/signal` pass together: 45 passed, 1 skipped.
- Still to do: entities already created from masked values remain in the database, and the cases they grouped need checking. I have not touched that data.

**5. Signal payload masking**
- The POST route stores the raw payload and commits it before any masking. Masking happens later in the processing flow. So the unmasked payload is written to the database.
- Masking applies at any depth and matches key names exactly, so `apiKey` and `access_token` are not masked by default.

UNPROTECTED_AT_START: case.create_case_channel, case.create_case_resources, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4