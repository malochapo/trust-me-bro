Five data-changing routes across the two files have no `PermissionsDependency` in their route definition.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST "/{case_id}/resources/conversation"` → `create_case_channel` (line 236)
3. `POST "/{case_id}/resources"` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE "/{incident_id}/event/{event_uuid}"` → `delete_custom_event` (line 503)

The check was on each route's own decorator, not on any router-level or `include_router` dependency. Both files use a bare `APIRouter()`, so there is no router-level dependency in these files. I did not look at how the routers are mounted elsewhere, which could add dependencies I haven't seen.

Every other POST, PUT, PATCH and DELETE route in the two files declares one. I made no code changes.

----- next turn -----

Yes, one of them was a regression: the incident `DELETE /{incident_id}/event/{event_uuid}` route (`delete_custom_event`). I've restored its permission check and added a test for it. I haven't committed anything.

**Why it's a regression:** commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed this line from the route, and the commit message doesn't mention it:
```python
dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))],
```
The sibling event routes (`POST` and `PATCH` on the same path family) still have it. The case-side `delete_custom_event` is guarded by `CaseEventPermission`.

**Not regressions:** `create_case_channel` and `create_case_resources` have had no permission check since they were added (`f08a22b3`, `ced74f33`). I treated those as original design. You may still want to decide whether they should be guarded.

**Changes:**
- `src/dispatch/incident/views.py`: put the `dependencies=[...IncidentEventPermission...]` line back on the route.
- `tests/incident/test_incident_event_permissions.py` (new): looks up the DELETE route on the incident router and asserts `IncidentEventPermission` is among its permission classes. The existing view tests call the view functions directly, so they would never notice a missing route dependency.

The new test passes with the fix. With the fix stashed, it fails. I ran only the new test file, not the full suite.

----- next turn -----

The cause is in `restricted_case_filter` (`src/dispatch/database/service.py`). Commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02) introduced it.

**Cause:** the commit took the `and_(...)` out of the visibility filter. The filter turned from this:
```python
or_(open, and_(restricted, participant_email == me))
```
into this:
```python
or_(open, restricted, participant_email == me)
```
That means any case with `Visibility.restricted` passes for every non-admin user, whether or not they participate. Users with the admin, owner or manager role skip this filter entirely. Anyone else, such as a member or a security-team user without one of those roles, sees every restricted case. The incident filter (`restricted_incident_filter`) still has the correct `and_`, so only cases were affected.

**Fix:** I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` grouping. I didn't change any tests. `tests/database` and `tests/case` pass (40 passed). I haven't committed anything.

I didn't add a new regression test, since you said the existing tests were correct, but I can add one for restricted-case visibility if you want it.

----- next turn -----



----- next turn -----

Yes, the unmasked payload is written to the database. The API request stores `raw` as received, and masking happens later in a separate step. I changed no code.

## Trace

1. **`POST /api/v1/{organization}/signals/instances`** is `create_signal_instance` in `src/dispatch/signal/views.py:70`.
   - It resolves the project and the signal definition, trying the payload's `externalId` or `variant` first, then the project's default signal.
   - It returns 404 if no definition is found.
   - The `background_tasks` argument is accepted but never used.
2. **`signal_service.create_instance`** (`signal/service.py:650`) builds the `SignalInstance`.
   - It sets `raw=json.loads(json.dumps(signal_instance_in.raw))`, a plain copy of the request body, with no masking.
   - It uses `raw["id"]` as the primary key, and returns 400 if that isn't a valid UUID.
   - It calls `db_session.add`.
3. **Back in the view**, `db_session.commit()` writes the row. A duplicate id gives a 409. The view returns the instance to the caller, with no case created yet.
4. **Asynchronous processing** is done by the scheduler process (`dispatch signals process` in `cli.py:937`, or the batch loop in `signal/flows.py`).
   - It picks up instances with `filter_action IS NULL` and `case_id IS NULL`, oldest first, up to 500 per pass.
   - Each one goes through `signal_instance_create_flow` (`signal/flows.py:46`).
5. **Inside `signal_instance_create_flow`**, in order:
   - **Masking:** `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60).
   - **Entities:** extracts entities from the payload, using the signal's entity types plus the scope-`all` ones, and commits.
   - **Filtering:** `signal_service.filter_signal` (`service.py:866`) applies snooze first, then deduplication, and commits. If either fires, `filter_action` is set and the flow returns. For a deduplicated instance that already has a case with a conversation, it updates the Slack signal message.
   - **Stops without a case:** canary instances, and signals with `create_case` off, are stored and returned.
   - **Case creation:** otherwise it resolves case type, priority, severity, oncall assignee and conversation target, with the instance taking priority over the signal, then the case type. It creates the case as `Visibility.open` and `CaseStatus.new`, links it, commits and runs `case_new_create_flow`. It then engages users if engagements are configured, and runs the signal's workflows.

## Masking

- **Function:** `redact_raw` in `src/dispatch/signal/redaction.py`, called from `signal/flows.py:60`.
- **Behaviour:** it returns a copy where the value of any matching key becomes `"[REDACTED]"`. Keys match case-insensitively, at any depth, inside dicts and lists. Only keys are checked, so a secret sitting under a different key name, or in a string value, is not masked.
- **Default keys:** `password`, `secret`, `api_key`, `session_token` and `authorization`. They come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which can be overridden by an environment variable holding a comma-separated list.
- **Exact match only:** a key like `db_password` or `Authorization-Header` is not masked.

## Is the unmasked payload written to the database?

**Yes.**
- **Stored raw:** the instance is committed with the original `raw` at step 3, before any redaction.
- **Window:** the row stays unmasked until the scheduler redacts it, and commits it at the entity step or in `filter_signal`. Until then, it can be read from the database or through `GET /signals/instances`.
- **Not redacted at all:** if the scheduler isn't running, or the flow raises before the first commit, the row keeps the secrets. The batch loop rolls back on error, so a failure leaves it unmasked and it gets retried.
- **Never redacted:** instances created through `signal/flows.py` `create_signal_instance` or `service.update_instance` (`service.py:737`) do not go through `redact_raw` on their own path.
- **API response:** the POST returns `SignalInstanceRead`, which includes `raw` (`models.py:394`), straight from the unmasked object. The caller gets back what they sent.
- **Stored unmasked elsewhere:** `create_instance` also copies the raw payload into nothing else, but the unmasked values are in the database in the window above, so any database backup or replica taken then holds them.

The fix would be to call `redact_raw` in `create_instance` before the row is built. I haven't made that change.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02) caused it. In `find_entities` in `src/dispatch/entity/service.py`, it changed `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. That kept only the first match. Any JSONPath that matches several fields, such as a wildcard or a recursive path, then produced one entity.

I reverted that line to `matches = jpath.find(signal_instance.raw)`, so it now matches the code before the commit. I didn't touch any tests. `python -m pytest tests/entity` gives 11 passed. I only ran `tests/entity`, not the full suite, and nothing is committed.

The commit's "perf" rationale doesn't hold here. The cost of `find` is the same either way, and slicing only discards results.

----- next turn -----

Masked values are now skipped during entity extraction, and the new test passes along with the rest of `tests/entity` (12 passed).

**Why unrelated instances were grouped:** the scheduler flow masks `raw` before it extracts entities (`signal/flows.py:60`, then `find_entities`). The "GitHub: Personal access token exposed" entity type's JSONPath points at `session_token`, which is one of the default masked keys. Every instance therefore yielded an entity with the value `"[REDACTED]"`. `get_by_value_or_create` reuses an existing entity with the same value, so all those instances shared one entity. The deduplication filter on that entity type then treated them as the same alert and grouped them into one case.

**Fix:** in `src/dispatch/entity/service.py`, the JSONPath extraction now skips any match whose value equals `MASK`, which it imports from `dispatch.signal.redaction`. I left the masking itself unchanged.
- `find_entities` is the only place entities are extracted from a payload, so this guard covers the whole path.
- Its regex-type parameter is currently unused, so there is no regex path to guard.

**Test:** I added `test_find_entities_ignores_masked_values` at the end of `tests/entity/test_entity_service.py`. I did not edit any existing test. It masks a payload with `redact_raw`, then checks that entity types pointing at `session_token` and at a nested `Password` (matched with `$..Password`) yield nothing, while an unmasked `asset[*].id` still yields `keep-me`.

**Check without the fix:** I stashed `src/dispatch/entity/service.py` and re-ran `tests/entity`. The new test failed. `test_find_entities_with_field_only` also failed, because that stash goes back to the committed file, which still has the earlier `[:1]` bug I fixed uncommitted.

**Not covered:**
- Instances already processed under the old behaviour keep their `"[REDACTED]"` entity and its case links. I did not clean those up.
- I ran only `tests/entity`, and nothing is committed.

----- next turn -----

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