Both investigations are in the recap below. The first was an audit of the case and incident APIs for data-changing routes without a permission check. It found one regression, which I fixed. The second was a restricted-case visibility leak, which I also fixed.

**Permission audit.** Before my changes, five POST/DELETE handlers had no `PermissionsDependency`:
- `case.create_case`, `case.create_case_channel`, `case.create_case_resources` and `incident.create_incident`.
- `incident.delete_custom_event`.

`case.create_case` and `incident.create_incident` are open on purpose, since anyone may report a case or incident. The incident `delete_custom_event` route is the regression. Commit `28c21e1e` removed its `IncidentEventPermission` check.

I restored the check in `src/dispatch/incident/views.py`. I added `tests/incident/test_incident_event_permissions.py`, which fails if the route loses `IncidentEventPermission`. I confirmed it passes with the fix and fails without it.

**Restricted cases visible to non-participants.** Commit `42699ebc` ("flatten the restricted case filter") dropped the `and_(...)` in `restricted_case_filter`. Every restricted case then matched for users without the admin, owner or manager role. I restored the grouping in `src/dispatch/database/service.py`. `tests/database` and `tests/case` pass (40 passed).

**Signal instance flow and masking.**
- **Request path:** `POST /signals/instances` stores the instance with its payload as received. The scheduler then picks it up, masks the payload, extracts entities, applies snooze and dedup filters, and either stops or creates a case.
- **Masking:** `redact_raw` in `dispatch.signal.redaction` runs in `signal_instance_create_flow`. It is also the only place that masks. The row is committed unmasked first, and the POST response echoes the unmasked `raw`. It matches keys exactly (case-insensitive, at any depth).
- **Introduced by:** `d2675cf4`.

**Entity extraction.** Commit `beb60cc4` ("stop at the first JSONPath match") sliced the match list to its first element, so JSONPaths matching several fields produced one entity. I reverted that line in `src/dispatch/entity/service.py`, and `tests/entity` went green.

**Masked values becoming entities.** Because masking runs before extraction, a JSONPath that points at a masked field (like `session_token`) produced an entity with the value `[REDACTED]`. All such instances shared one entity, so the dedup filter grouped them into one case. I now skip matches equal to `MASK`, and added `test_find_entities_ignores_masked_values` to `tests/entity/test_entity_service.py`. `tests/entity` gives 12 passed.

**Not done:**
- I ran only `tests/database`, `tests/case`, `tests/entity` and the new incident test, not the full suite.
- Nothing is committed.
- Instances already deduplicated under the old behaviour were not cleaned up.
- The unmasked write at POST time is not fixed. The fix would be to redact in `create_instance`.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4