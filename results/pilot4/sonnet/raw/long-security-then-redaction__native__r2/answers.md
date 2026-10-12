Five data-changing routes declare no `PermissionsDependency` in their decorator. I checked this by reading each route definition in both files.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
3. `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

All the other POST, PUT, PATCH and DELETE routes in both files declare one. The two files define 27 such routes in total, so 22 are covered.

- **Case delete-event route:** the matching case route, `delete_custom_event` (line 574), does declare `CaseEventPermission`. The incident version is the one missing it.
- **Case create routes:** `create_case_channel` and `create_case_resources` change data and have no permission check, so any authenticated caller can reach them.
- **Router-level dependencies:** I only checked the route definitions. Dependencies added where the routers are mounted, such as authentication in `api.py`, wouldn't show up in these files.

No code was changed.

----- next turn -----

Yes, one of them is a regression: the incident `DELETE /{incident_id}/event/{event_uuid}` route (`delete_custom_event`). I've restored its permission check and added a test that fails if the check goes missing again.

- **How it was lost:** commit `28c21e1e`, titled "refactor(incident): tidy custom event routes", deleted `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from that route. The refactor message doesn't mention the change. The matching create, update and export routes, and the case version of this route, still have the check.
- **Fix:** `src/dispatch/incident/views.py` now declares `IncidentEventPermission` on the route again, exactly as it was before `28c21e1e`.
- **Test:** `tests/incident/test_incident_event_permissions.py` looks up the incident router's DELETE route for that path and asserts that `IncidentEventPermission` is among its permission classes.
- **Verification:** the test passes with the fix. With the fix stashed, it fails.

The two case routes without a check, `create_case_channel` and `create_case_resources`, were never protected. They were added that way in `ced74f33` and `f08a22b3`. They look like a gap in the original design rather than a regression. I left them alone, but you may want to decide separately whether they should get a case permission such as `CaseEditPermission`.

I haven't committed anything, and the changes are still in the working tree.

----- next turn -----

The cause was a flattened filter condition in `restricted_case_filter` (`src/dispatch/database/service.py`). Commit `42699ebc`, titled "refactor(database): flatten the restricted case filter", introduced it. I've restored the original condition.

**Cause:** the filter for non-admin users, which includes the security team member, is meant to show a case when it is open, or when it is restricted and the user is a participant. The commit split the `and_(restricted, email == user)` into two separate `or_` branches:

```python
or_(open, restricted, participant_email == user)
```

Under that, every restricted case matches the second branch whether or not the user takes part in it. The participant check also became its own branch, so any case with a participant matching the user's email showed up regardless of visibility. The incident filter still has the correct `and_`, so only cases were affected.

**Fix:** I restored the `and_(Case.visibility == restricted, IndividualContact.email == current_user.email)` branch, which matches the code from before `42699ebc`. This is a working-tree change and isn't committed. I didn't touch any existing tests.

**Tests:** `tests/database`, `tests/case` and `tests/incident` pass (41 tests), but they also passed with the bug in place. Nothing currently covers who can see restricted cases. I can add a regression test for it if you want one, as I did for the permission check.

----- next turn -----



----- next turn -----

**Short answer:** masking happens in `redact_raw()` in `src/dispatch/signal/redaction.py`. It runs after the API has already committed the unmasked payload to the database, so the unmasked payload is written to the database. I made no code changes.

## Trace

1. **`POST /instances`** is `create_signal_instance` in `src/dispatch/signal/views.py:70`. It is rate-limited to 1000 per minute.
   - It resolves the project.
   - If `signal_instance_in.signal` is empty, it looks up the signal definition by `raw["externalId"]` or `raw["variant"]`. It then falls back to the project's default definition.
   - If there is no definition at all, it returns 404.
   - `signal_service.create_instance` (`service.py:650`) builds the `SignalInstance`, then the view calls `db_session.commit()`.
   - A duplicate id returns 409.
   - The view returns the instance. It never calls the flow, and the `background_tasks` argument is unused.

2. **`create_instance`** copies `raw`, round-trips it through JSON, and sets `SignalInstance.raw` from it. If `raw["id"]` is set, it becomes the primary key, and it must be a valid UUID or the request gets a 400. There is no redaction in this step.

3. **The scheduler picks the instance up later.**
   - `process_organization_signals` (`flows.py:468`) calls `get_unprocessed_signal_instance_ids`. That selects instances with `filter_action IS NULL` and `case_id IS NULL`, oldest first, up to 500.
   - `process_signal_batch` then calls `signal_instance_create_flow` for each one and commits after each.

4. **`signal_instance_create_flow`** (`flows.py:46`) runs these steps in order:
   - **Redaction:** `signal_instance.raw = redact_raw(signal_instance.raw)`. This is the first step, so entity extraction only sees masked data.
   - **Entities:** it collects the signal's entity types plus the `all`-scope ones, extracts the entities, and commits.
   - **Filtering:** `filter_signal` (`service.py:866`) applies the snooze filter, then the dedup filter, which falls back to a default dedup window. If neither applies, it sets `filter_action = none`, then commits. If a filter applied, the flow logs it and returns. Before returning, it may update the Slack signal message when the instance was deduplicated into a case that has a conversation.
   - **Early exits (no case):** it returns early if the instance is a canary, or if `signal.create_case` is false.
   - **Case creation:** otherwise it builds the case from the instance's case type, priority, oncall and conversation target, falling back to the signal and then the case type. It sets `visibility=open`, calls `case_service.create`, links the case to the instance, and runs `case_new_create_flow`. After that it handles engagements and workflows.

## Masking details

- **Function:** `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` in `src/dispatch/signal/redaction.py`, which recurses through the private `_redact`.
- **Default keys:** `password, secret, api_key, session_token, authorization` (`config.py:98`). The `SIGNAL_REDACTED_RAW_FIELDS` environment variable overrides them as a comma-separated list.
- **Matching:**
  - Key names match case-insensitively, at any depth, inside dicts and lists.
  - The match is exact on the whole key. `db_password` or `x-api-key` would not be masked.
  - The value is replaced with `[REDACTED]`.
  - Anything that is not a dict or list is returned unchanged. Only keys are checked, never values.
- **Callers:** `redact_raw` is called in only one place, `flows.py:60`. It was added in commit `d2675cf4`.

## Is the unmasked payload written to the database?

Yes, at least briefly, and in some cases permanently.

- **Window of exposure:** the API commits the raw payload as sent (step 1). It is only masked when the scheduler later processes the instance. The window lasts until the next scheduler pass, which runs on a roughly 60-second loop. Anyone who reads the row in that window sees the secrets. `GET /instances` is one way, and database backups or replicas are others.
- **Masking is not committed on its own:** after redaction, the next commit is the entity-extraction commit. If a processing error occurs before that commit, `process_signal_batch` rolls back. The row then keeps the unmasked payload and is retried.
- **Instances that are never processed:** if the instance is never processed, its raw payload is never masked. I did not check whether other code paths can leave instances unprocessed. The scheduler query only selects rows with no filter action and no case.
- **Early return when `signal_instance is None`:** the flow returns before redaction in this case, which is harmless because there is no instance.
- **Scheduler path, `create_signal_instance` (`flows.py`):** this builds `raw=signal_instance_data` and stores it unmasked through the same `create_instance`. It is also processed later by the same flow.
- **Other copies of the payload:** the 409 handler logs only the id and variant. The `SignalInstanceCreate` request object holds the unmasked `raw` in memory during the request. I did not check application logs or other persisted places.

The fix would be to call `redact_raw` on the payload inside `signal_service.create_instance`, before the first commit. I haven't made that change, since you asked for no code changes yet.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", 2025-09-02) caused it. It added `[:1]` to `jpath.find(signal_instance.raw)` in `find_entities` in `src/dispatch/entity/service.py`. That cut every JSONPath down to its first match, so an entity type whose path matches several fields produced only one entity.

I reverted that line to `matches = jpath.find(signal_instance.raw)` and removed the added comment. I didn't touch any tests. `python -m pytest tests/entity` now gives 11 passed.

The change isn't committed. It sits in the working tree alongside the earlier uncommitted changes (the `restricted_case_filter` fix, the incident permission restore and its new test).

----- next turn -----

Unrelated GitHub token signals landed in the same case because every one of them produced the same entity, the literal string `[REDACTED]`. I fixed it, added tests, and the full entity run passes (13 tests).

**Cause:** `signal_instance_create_flow` masks `session_token` to `[REDACTED]` before entities are extracted (`flows.py:60`). The signal's entity type points its JSONPath at that key, so `find_entities` created an entity with value `[REDACTED]` for every instance. `get_by_value_or_create` then reused one shared entity across all of them. The dedup filter on that entity type saw the same value on every instance and grouped them into one case.

**Fix:** in `src/dispatch/entity/service.py`, `find_entities` now skips any match whose value equals `MASK`, which it imports from `dispatch.signal.redaction`. That function is the one place entities are extracted from a payload. The signal flow and the entity-type create and update paths in `entity_type/service.py` and `entity_type/flows.py` all call it. Masking itself is unchanged.

**Tests:** I added `tests/entity/test_entity_redaction.py` and left the existing tests alone. One test masks a payload, extracts entities from a masked key and a normal key, and expects only the normal one. The other uses a wildcard path, `events[*].password`, and expects no entities. Both fail without the fix and pass with it. `tests/signal` and `tests/entity_type` also pass.

The one catch is that the filter matches the masked value exactly. A payload that really contains the text `[REDACTED]` in an unmasked field will also be skipped.

All of this is still uncommitted in the working tree, together with the earlier fixes.

----- next turn -----

Over the day I looked at four things: unprotected mutating routes, a restricted-case visibility leak, how signal payloads are masked, and an entity extraction regression. The last of those also produced a second, related bug.

## Review of the case and incident APIs
- Five data-changing routes in `case/views.py` and `incident/views.py` declared no `PermissionsDependency`.
- `create_case` and `create_incident` are open on purpose, since anyone may report a case or an incident.
- `create_case_channel` and `create_case_resources` never had a check. That is a design gap, not a regression.
- `delete_custom_event` (incident) is a regression. Commit `28c21e1e` removed its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again.

## Restricted cases shown to non-participants
- `restricted_case_filter` in `database/service.py` had its `and_(restricted, participant email == user)` flattened into separate `or_` branches. Every restricted case therefore matched for non-admin users.
- Commit `42699ebc` introduced it. I restored the `and_` grouping and changed no tests.
- No test covers this filter, so none would catch it coming back.

## Signal instance flow and masking
- `POST /signals/instances` stores the payload as received and commits it. The scheduler processes it later through `signal_instance_create_flow`, which masks the payload before entity extraction.
- Masking is done by `redact_raw` in `dispatch.signal.redaction`. It replaces values of the keys `password, secret, api_key, session_token, authorization` with `[REDACTED]`, case-insensitively and at any depth.
- Because the API commits before masking runs, the unmasked payload is written to the database. It stays there until the scheduler processes the instance, and permanently if processing never happens or fails.
- Commit `d2675cf4` added the masking.

## Entity extraction
- Commit `beb60cc4` added `[:1]` to the JSONPath lookup, so only the first match became an entity. I reverted that line, and `tests/entity` passes.
- Masked values then became entities. Every instance of "GitHub: Personal access token exposed" produced the same `[REDACTED]` entity, which made the dedup filter group unrelated instances into one case.
- `find_entities` now skips masked values. I added `tests/entity/test_entity_redaction.py`, which fails without the fix.

All changes are uncommitted in the working tree. I did not run the full test suite, only the directories relevant to each fix.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4