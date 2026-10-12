Here is the recap for the weekly report. Nothing from today is committed.

## Investigation 1: permissions and visibility in the case and incident APIs

**Unguarded routes.** I listed every POST/PUT/PATCH/DELETE route without a `PermissionsDependency`. There were five. They are:
- `case.create_case`
- `case.create_case_channel`
- `case.create_case_resources`
- `incident.create_incident`
- `incident.delete_custom_event`

**Open by design:** `create_case` and `create_incident`, because anyone may report a case or incident.

**Regression:** `incident.delete_custom_event`. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check.
- I restored the check.
- I added `tests/incident/test_incident_views.py`, which fails if the check goes missing again.

**Left open:** `case.create_case_channel` and `case.create_case_resources` appear never to have had a check. They look like a design gap rather than a regression, so I left them. The incident equivalent, `create_incident_resources`, uses `IncidentViewPermission`. Whether the case routes should be guarded is a policy decision for you.

**Restricted cases visible to non-participants:** commit `42699ebc` ("refactor(database): flatten the restricted case filter") broke `restricted_case_filter` in `src/dispatch/database/service.py`. It split the `restricted and email == user` condition into separate `or_` branches, so every restricted case matched. I restored the `and_` grouping. I changed no existing tests, and I did not add a regression test for this one.

## Investigation 2: signal instances, masking and entities

**Flow** for `POST /signals/instances`:
1. The view stores the instance and commits it.
2. A worker (`dispatch signals process`) later picks it up and masks the payload.
3. The worker extracts entities, then runs the snooze and dedup filters.
4. Instances that pass the filters open a case, unless the signal is a canary or has case creation off.

**Masking:** `dispatch.signal.redaction.redact_raw` does it, replacing values with `[REDACTED]`.
- Keys match case-insensitively and exactly, at any depth.
- The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- The `SIGNAL_REDACTED_RAW_FIELDS` environment variable overrides the list.

**Unmasked payload in the database:** yes. `create_instance` stores the raw payload as sent and the view commits it. The worker masks it later, and if the worker fails before its first commit, the row stays unmasked. I recommended calling `redact_raw` inside `create_instance`, but I made no change for that.

**Entity extraction:** commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") sliced matches to `[:1]`, so a JSONPath matching several fields produced only one entity. I removed the slice, and `tests/entity` passes.

**Wrongly grouped GitHub token cases:** the session-token JSONPath matched the masked value `[REDACTED]`. It became one entity shared by every instance, and the dedup filter grouped them on it.
- `find_entities` now skips masked values.
- I added `tests/entity/test_entity_redaction.py`, which fails without the fix.
- Entities and cases created before the fix are not cleaned up.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95