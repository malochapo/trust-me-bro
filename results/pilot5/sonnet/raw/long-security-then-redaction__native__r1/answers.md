Five data-changing routes declare no `PermissionsDependency` in their route definition. Every other POST, PUT, PATCH and DELETE route in the two files declares one. I haven't changed any code.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
3. `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

The first four are create routes, so they may be intentionally open to any authenticated user. The case-resources and channel routes act on an existing case, though, so they are more worth a look. The incident `delete_custom_event` route stands out most. Its case counterpart and the other incident event routes all use the event permission, and this one doesn't.

I only checked each route's own decorator and arguments. I didn't check whether permissions are applied at the router level, for example in `include_router` calls. I also didn't check for authentication middleware, so these routes may still require a logged-in user.

----- next turn -----

Yes, one of them is a regression: the incident `DELETE /{incident_id}/event/{event_uuid}` route (`delete_custom_event`). I restored its permission check and added a test. I haven't committed anything.

- **The regression:** commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from that route. The commit message calls it a tidy-up, but it dropped the permission check, so any authenticated user could delete incident timeline events.
- **Not regressions:** `create_case_channel` and `create_case_resources` in the case API never had a permission check in their history. They have been unguarded since they were added, in `f08a22b3` and `ced74f33`. They may still be worth guarding, but that would be a new decision, not a fix.
- **The fix:** I put the `dependencies=[...]` line back in `src/dispatch/incident/views.py`, with the same `IncidentEventPermission` the route had before.
- **The test:** `tests/incident/test_incident_view_permissions.py` looks up that route on the router and asserts it has a `PermissionsDependency` containing `IncidentEventPermission`.
- **Verification:** the test passes with the fix. It fails when I stash the change to `views.py`, so it does catch the check going missing again.

I only ran the new test, not the rest of the suite.

----- next turn -----

The cases list was leaking restricted cases because of a bad refactor in `restricted_case_filter` (`src/dispatch/database/service.py`). That bug came in with commit `42699ebc`, "refactor(database): flatten the restricted case filter", from Sep 2, 2025.

**Cause:** the filter for non-admin users is meant to read "open, or restricted and I'm a participant". The refactor removed the `and_(...)` wrapper. The condition became three separate alternatives: open, or restricted, or I'm a participant. Every restricted case therefore matched on its own, whether or not the user took part. The incident filter still has the correct `and_` form.

**Fix:** I put the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` wrapper back. Admin, owner and manager roles are unaffected.

**Tests:** the existing tests are unchanged. `tests/database` and `tests/case` pass (40 tests). I didn't run the rest of the suite.

The working tree now holds two uncommitted changes: this fix and the earlier incident permission fix with its test.

----- next turn -----



----- next turn -----

Yes, the unmasked payload is written to the database. The view stores it first, and masking only happens later in a separate worker step. I made no code changes.

## The trace

1. **The API view** is `create_signal_instance` in `src/dispatch/signal/views.py:70`.
   - It resolves the project, then the signal definition. It looks for `externalId` or `variant` in `raw`, falls back to the default definition, and returns 404 if there is none.
   - It calls `signal_service.create_instance(...)` and then `db_session.commit()`.
   - `create_instance` (`signal/service.py:650`) copies `raw`, drops `oncall_service`, and round-trips it through JSON. It does not mask anything.
   - The view returns the instance. It declares a `BackgroundTasks` parameter but never uses it, so no processing happens in the request.

2. **The worker picks it up later.** `process_organization_signals` (`signal/flows.py`) loops over instances whose `filter_action` is still NULL, via `get_unprocessed_signal_instance_ids`. It calls `signal_instance_create_flow` for each one and commits. The CLI scheduler loop at `cli.py:1004` does the same.

3. **Masking** is the first step of `signal_instance_create_flow` (`flows.py:60`): `signal_instance.raw = redact_raw(signal_instance.raw)`. It runs before entity extraction, so entities are only extracted from the masked payload.

4. **Filtering.** `filter_signal` (`signal/service.py:866`) applies the snooze filter first, then the dedup filter. If either one acts, the flow logs it, updates the Slack signal message if a case already exists, and returns. Otherwise `filter_action` is set to `none`. The flow also returns early with no case if:
   - the signal is a canary, or
   - the signal definition has `create_case` off.

5. **Case creation.** Otherwise the flow resolves the case type, priority, oncall assignee and conversation target. It builds a `CaseCreate` with open visibility and calls `case_service.create`. It then links the case to the instance and goes on to the case creation flow.

## The masking function

- **Where:** `redact_raw` in `src/dispatch/signal/redaction.py`, added by commit `d2675cf4`.
- **How it works:**
  - It returns a copy of the payload.
  - It walks dicts and lists at any depth.
  - It matches keys case-insensitively and exactly. A key named `db_password` is not masked, because there is no substring match.
  - It replaces the value with `"[REDACTED]"`.
- **Default keys** come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`: `password`, `secret`, `api_key`, `session_token`, `authorization`. You can override them with an environment variable holding a comma-separated list.

## Is the unmasked payload written to the database?

Yes. The view commits the raw payload as received (step 1) before any masking.

- **Exposure window:** the secrets stay in the `raw` JSONB column until the worker processes that instance. That can be about `LOOP_DELAY` (60 seconds) or longer if there is a backlog.
- **The API response:** the POST response is built from the same unmasked instance. `SignalInstanceRead` is the response model, and I didn't check that it includes `raw`. If it does, the secrets go straight back to the caller.
- **Failures:** if the flow throws an exception, `process_signal_batch` rolls back. The instance then stays unmasked and unprocessed, and is retried on the next loop.
- **Other reads:** the GET `/instances` list is not guarded by the masking either. It can return raw payloads that haven't been masked yet.
- **Where masked data ends up:** the masked copy is committed at the first `db_session.commit()` after entity extraction, overwriting the original in the same row. I did not check whether the database keeps history of the old value, such as WAL or audit tables.

## Related observation

At `flows.py:46` the log call uses `"%%s"`, which looks like a typo for `"%s"`, so the id is never logged.

If you want the unmasked payload never to reach the database, the fix would be to call `redact_raw` in `create_instance` or in the view, before the commit. I haven't changed anything.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, Sep 2 2025) caused it. It changed `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]` in `find_entities` (`src/dispatch/entity/service.py`). Any JSONPath that matches several fields, such as `$.users[*].email`, then produced only one entity.

I reverted that one line and left a comment-free `matches = jpath.find(signal_instance.raw)`. `python -m pytest tests/entity` now gives 11 passed. I didn't change any tests, and I didn't run the rest of the suite.

The changes from the earlier requests (the incident permission fix with its test, and the restricted-case filter fix) are still uncommitted in the working tree, alongside this one.

----- next turn -----

Unrelated "GitHub: Personal access token exposed" instances were being grouped because the masking step turned every token into the same entity value.

**Cause:** `signal_instance_create_flow` calls `redact_raw` first, so `session_token` becomes `"[REDACTED]"` in every instance. Entity extraction then ran on the masked payload. The entity type whose JSONPath points at the token produced the same entity, `"[REDACTED]"`, for every instance. The dedup filter on that entity type saw them all as identical and merged them into one case.

**Fix:** `find_entities` in `src/dispatch/entity/service.py` now skips any match whose value is the mask, `MASK` from `dispatch.signal.redaction`. All extraction goes through this one function. That covers the signal flow, `entity_type/flows.py` and the re-extraction in `entity_type/service.py`. The masking itself is unchanged.

**Test:** the new `tests/entity/test_entity_masked_values.py` masks a payload with `redact_raw`, then extracts entities for a `session_token` type and a `user.login` type. Only the `user.login` entity comes back. The test fails without the fix. `tests/entity` and `tests/signal` pass (the new test is included, one test skipped, as before).

With the token entity gone, the dedup filter on that entity type has nothing to match on. Whether those instances still group depends on how the filter treats instances that have no entity of that type. I didn't check that, so it is worth a look at the signal's filter configuration.

Everything is still uncommitted.

----- next turn -----

## Recap

**Investigation 1: permission checks (security review)**
- Five data-changing handlers had no `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, because anyone may report a case or an incident.
- `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") dropped its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_view_permissions.py`, which fails if the check goes missing again.
- `create_case_channel` and `create_case_resources` never had a check, so they are not regressions. They are a possible hardening item.

**Investigation 2: restricted cases shown to non-participants**
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_` in `restricted_case_filter`. Every restricted case then matched for non-admin users. I restored the `and_`, and the existing tests are untouched.

**Investigation 3: signal masking**
- `redact_raw` in `dispatch.signal.redaction` masks values to `[REDACTED]`, matching keys case-insensitively and exactly, at any depth. Commit `d2675cf4` introduced it.
- The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`. They can be overridden with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable.
- The API view commits the payload as received. Masking only happens later, in the worker's `signal_instance_create_flow`. So the unmasked payload is written to the database, briefly.

**Investigation 4: entity extraction**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") kept only the first match. I reverted the line, and `tests/entity` is green again.
- Separately, masked tokens all became the same `[REDACTED]` entity, which grouped unrelated GitHub token instances into one case. `find_entities` now skips masked values, and `tests/entity/test_entity_masked_values.py` covers it.

All changes are uncommitted. I only ran `tests/database`, `tests/case`, `tests/entity` and `tests/signal`, not the full suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95