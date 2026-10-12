Four state-changing routes declare no `PermissionsDependency` in their route definition. I found them by reading the decorators in both files. Both routers are plain `APIRouter()` instances with no router-level dependencies.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` (`create_case`, line 162)
2. `POST "/{case_id}/resources/conversation"` (`create_case_channel`, line 260)
3. `POST "/{case_id}/resources"` (`create_case_resources`, line 260; the decorator spans lines 260–265)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` (`create_incident`, line 117)
5. `DELETE "/{incident_id}/event/{event_uuid}"` (`delete_custom_event`, line 503)

That makes five routes: three in the case API and two in the incident API.

I only checked each route's own decorator. Other protection, such as authentication middleware applied where the routers are mounted in `api.py`, would not show up here, and I did not check for it.

I did not change any code.

----- next turn -----

Yes, one of them is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`) in the incident API. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. The sibling create, update and export event routes still have it.

I put the check back in `src/dispatch/incident/views.py`, the same line that commit deleted.

I added `tests/incident/test_incident_views.py`. It finds the DELETE route and asserts that `IncidentEventPermission` is among its permission classes. With the fix it passes. With the fix stashed it fails, so it does catch the check going missing. I only ran that file, not the full suite.

The two case routes, `POST /{case_id}/resources/conversation` and `POST /{case_id}/resources`, are not regressions. They were added without a permission check in `f08a22b3` and `ced74f33`. Whether they should have one is a design question I left alone. They let any caller create resources or a channel for any case, so you may want to look at them.

Nothing is committed.

----- next turn -----

The security team member was seeing restricted cases because commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02) broke the case visibility filter. I've fixed it and left the existing tests alone.

**Cause.** In `restricted_case_filter` (`src/dispatch/database/service.py`), the commit removed the `and_(...)` around the restricted-case condition. The filter became:

```
open OR restricted OR email == current_user
```

Every restricted case now passes the `visibility == restricted` branch, whether or not the user takes part in it. Admins, owners and managers skip this filter, so only other roles were affected, including the security team member.

**Fix.** I restored the original grouping: `open OR (restricted AND email == current_user)`.

**Tests.** `tests/database` and `tests/case` pass (40 tests). The existing tests don't seem to have caught this regression, so I did not add a new one. Say if you want one for the non-participant case.

I haven't committed anything. The working tree now holds this fix and the earlier incident permission fix and test.

----- next turn -----



----- next turn -----

**Short answer:** masking is done by `redact_raw()` in `src/dispatch/signal/redaction.py`. It runs after the instance has been committed, so the unmasked payload is written to the database first. The masked copy replaces it a moment later.

## Trace of `POST /api/v1/{organization}/signals/instances`

1. **Request handler:** `create_signal_instance` in `src/dispatch/signal/views.py:70`.
   - It resolves the project.
   - It finds the signal definition by `externalId` or `variant` in `raw`, falling back to the project's default signal. If there is none, it returns 404.
   - It calls `signal_service.create_instance(...)` and then `db_session.commit()`. A duplicate id gives 409.
   - It returns the instance. The `BackgroundTasks` parameter is declared but never used, so nothing is processed in the request.
2. **Persisting:** `create_instance` (`src/dispatch/signal/service.py:649`) stores `raw=json.loads(json.dumps(signal_instance_in.raw copy))`. `oncall_service` is popped from the stored raw when it is set. **No masking happens here.**
3. **Picking up later:** the instance is processed by a polling loop, not by the request.
   - `process_signal_batch` and `process_organization_signals` in `src/dispatch/signal/flows.py:~390` and the loop in `src/dispatch/cli.py:~1004` select instances where `filter_action IS NULL AND case_id IS NULL`.
   - They call `signal_instance_create_flow` for each, with a commit per instance.
4. **`signal_instance_create_flow`** (`flows.py:46`):
   - **Masking:** `signal_instance.raw = redact_raw(signal_instance.raw)` at `flows.py:60`, before entity extraction.
   - **Entities:** it merges the signal's entity types with the `all`-scoped ones and runs `entity_service.find_entities`. This reads the already-masked `raw` through JSONPath, then commits.
   - **Filtering:** `signal_service.filter_signal` runs a snooze filter, then a dedup filter. If either matches, `filter_action` is set and the instance is filtered out.
     - A filtered instance linked to an existing case may update that case's Slack signal message.
     - Otherwise `filter_action` is set to `none` and processing continues.
   - **Early exits (instance stored, no case):** a canary signal, or a signal with `create_case` off.
   - **Opening a case:** otherwise it resolves case type, priority, oncall service and conversation target, with the instance taking priority over the signal and the signal over the case type. It builds `CaseCreate` and calls `case_service.create`. Then it runs `case_new_create_flow`, the identity engagement if configured, and any workflows.

## Masking details

- **Function:** `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)`, with the private recursive helper `_redact`.
- **Behaviour:**
  - It returns a copy. Any key whose name is in the field list has its value replaced with `"[REDACTED]"`.
  - Matching is case-insensitive, on key names only, and works at any depth, inside dicts and lists.
  - It never inspects values, so a secret stored under an unlisted key is not masked.
- **Default keys** (`src/dispatch/config.py:98`): `password`, `secret`, `api_key`, `session_token`, `authorization`. They can be overridden with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable, as a comma-separated list. Overriding replaces the defaults rather than adding to them. Names are only stripped and lowercased, so there is no substring match. `client_secret` or `apiKey` would not be masked.
- **Added by:** commit `d2675cf4` ("feat(signal): mask sensitive raw fields before processing").

## Is the unmasked payload written to the database?

Yes. The request handler commits the original `raw` at step 1, and the instance stays in the database in that form until the poller reaches it. In `signal_instance_create_flow`, `raw` is replaced and committed by the entity commit or the `filter_signal` commit. The raw payload sits unmasked in the `signal_instance` table for at least that window.

It stays unmasked if the instance is never processed. That can happen when the scheduler isn't running, when the flow raises before the commit (the loop rolls back and the row remains unmasked, to be retried), or on the scheduler path, `flows.create_signal_instance` (`flows.py:231`), which also stores raw unmasked.

The `POST` response, built from the committed instance, also returns the unmasked `raw`.

## Side findings

- In the view, `signal_definition` is only assigned inside `if not signal_instance_in.signal:`. If the client supplies a signal, the next check raises `UnboundLocalError`. `external_id` and `variant` have the same problem.
- `flows.py:55` logs with `"%%s"`, which is a typo and prints a literal `%s`.

I haven't changed any code. Moving the `redact_raw` call into `create_instance` would fix the write-before-mask window, if you want that.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02) caused it, and I've reverted its change. `tests/entity` now passes, 11 tests.

The commit changed `find_entities` in `src/dispatch/entity/service.py` from `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. That cut every JSONPath result down to its first match. Expressions that match several fields, such as `$.users[*].email` or a recursive `$..ip`, therefore produced only one entity.

The commit was labelled a performance change, but `find()` already computes all matches before the slice. The slice saved nothing and only dropped results.

I removed the `[:1]` slice and the comment that justified it. No tests were changed. The working tree still holds the earlier uncommitted fixes, and nothing is committed.

----- next turn -----

Unrelated "GitHub: Personal access token exposed" instances were grouped because the masked placeholder became an entity value. I fixed that, and `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**Cause.**
- `signal_instance_create_flow` runs `redact_raw`, which replaces `session_token` with `"[REDACTED]"`. This happens before entities are extracted.
- The entity type's JSONPath then points at that key, finds the string `"[REDACTED]"`, and `find_entities` turns it into an entity.
- `get_by_value_or_create` returns the same entity for every instance, so the dedup filter on that entity type sees every instance as a duplicate and groups them into one case.
- This follows from the masking design in `d2675cf4`. Nothing in the extraction code checked for the placeholder.

**Fix.** In `src/dispatch/entity/service.py`, `find_entities` now skips any match whose value equals `MASK`, imported from `dispatch.signal.redaction`. I didn't touch the masking. `find_entities` is the only place that extracts entities from a payload, and it is called from three places:
- the signal flow;
- `entity_type.service.create`, when a new entity type is back-filled onto a case's existing instances;
- `entity_type/flows.py`.

All three are covered by this one check.

**Test.** I added `test_find_entities_skips_masked_values` to `tests/entity/test_entity_service.py`. It masks a payload with `redact_raw`, points entity types at `session_token` and `user.name`, and expects only `alice`. It is an addition, and no existing test was edited. With the fix stashed the new test fails, as expected.

**Existing instances.** Instances already processed may still be linked to a `"[REDACTED]"` entity. That entity stays in the database and keeps linking old instances, and I didn't clean it up. A one-off deletion of entities with that value would remove it. Say if you want that.

Nothing is committed. The working tree also still holds the earlier incident permission fix, the restricted-case filter fix and the entity first-match revert.

----- next turn -----

## Recap

### Investigation 1: signal instance flow and masking
`POST /api/v1/{organization}/signals/instances` does not process the instance in the request.
- **Request.** The handler resolves the project and the signal definition, calls `create_instance` and commits. A scheduler loop later picks up instances where `filter_action` and `case_id` are both null.
- **Flow.** `signal_instance_create_flow` masks the payload, extracts entities, then applies the snooze and dedup filters. A filtered instance stops there. Otherwise it is stored without a case if it is a canary or `create_case` is off, or it opens a case.
- **Masking.** `redact_raw` replaces the value of any key in the field list with `"[REDACTED]"`. Matching is case-insensitive, on key names only, at any depth. The masking was introduced by `d2675cf4`.
- **Defaults.** The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- **Unmasked data in the database.** The request handler commits the original payload before the scheduler masks it. The scheduler path stores it unmasked too, and an instance that is never processed stays unmasked. The `POST` response also returns the unmasked payload.

### Investigation 2: what broke this week
- **Missing permission check.** In the case and incident views, five handlers changed data without a `PermissionsDependency`:
  - `create_case` and `create_incident` are open on purpose, because anyone may report a case or an incident.
  - `create_case_channel` and `create_case_resources` have never had a check. I flagged them as a possible design gap and left them as they are.
  - `delete_custom_event` is the regression. Commit `28c21e1e` ("tidy custom event routes") dropped its `IncidentEventPermission`. I restored it and added `tests/incident/test_incident_views.py`.
- **Restricted cases visible to non-participants.** Commit `42699ebc` flattened `restricted_case_filter` and removed the `and_`, so every restricted case matched. I restored the grouping.
- **Entity extraction keeping only the first match.** Commit `beb60cc4` sliced the JSONPath results to `[:1]`. I removed the slice.
- **Dedup grouping unrelated instances.** The masked `"[REDACTED]"` value was becoming an entity, so unrelated instances shared one entity. `find_entities` now skips masked values, and I added a test for it.

Nothing is committed. Existing tests were not changed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4