Five data-changing routes across the two files have no `PermissionsDependency` in their route definition. I checked every POST, PUT, PATCH and DELETE route in both files, and I confirmed the five by reading their route decorators.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162).
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236).
3. `POST /{case_id}/resources` → `create_case_resources` (line 260).

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117).
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503).

The matching case route, `delete_custom_event` at line 574, does declare `CaseEventPermission`. The incident version is the odd one out.

I only looked at the `dependencies=[...]` argument on each route. Other protection could exist elsewhere, such as router-level dependencies in `api.py` or authentication middleware, so these five may still require a logged-in user. They just have no per-route permission check.

I haven't changed any code.

----- next turn -----

Yes, one of the five was a regression: the incident `DELETE /{incident_id}/event/{event_uuid}` route (`delete_custom_event`). I restored its check and added a test that fails without it. Nothing is committed.

**Cause:** commit `28c21e1e` ("refactor(incident): tidy custom event routes") deleted `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from that route. The commit message calls it a tidy-up, but it dropped a permission check. The sibling event routes (create, update, export) and the case equivalent still have `IncidentEventPermission` or `CaseEventPermission`.

**Fix:** I put the same dependency line back in `src/dispatch/incident/views.py`.

**Test:** `tests/incident/test_incident_views.py` looks up the DELETE route on the incident router and asserts it declares `IncidentEventPermission`. It checks the route definition, so it needs no database.
- With the fix, `tests/incident` and `tests/case` pass (16 tests).
- With the fix stashed, the new test fails.

**The two remaining case routes:** I found no regression, and I'm not sure they're intended.
- `create_case_channel` and `create_case_resources` have no permission check in the history I traced for them. They were added without one in `ced74f33` and `f08a22b3`.
- They let any authenticated caller create resources, or a dedicated channel, for any case. That's a gap, but a different kind from the incident one, so I left them alone. Adding `CaseEditPermission` would be a new check, not a restoration, so say if you want it.

Early test runs showed `ModuleNotFoundError` for `slack_sdk` and `dispatch`. The output condenser was garbling the results, and `rtk proxy python -m pytest` ran normally.

----- next turn -----

Fixed: commit `42699ebc` ("refactor(database): flatten the restricted case filter") introduced the bug. The tests in `tests/database`, `tests/case` and `tests/incident` pass (41 tests). I didn't change any existing tests.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` applies to every role except admin, owner and manager. The commit rewrote its condition from this:

```python
or_(open, and_(restricted, participant_email == me))
```

to this:

```python
or_(open, restricted, participant_email == me)
```

That made `Case.visibility == restricted` a standalone branch, so every restricted case matched for every non-admin user, whether or not they were a participant. The email condition also became its own branch, so it no longer limited anything. The security team member is probably a plain member role, so they got no filtering. `restricted_incident_filter` was untouched and still has the `and_`.

**Fix:** I put the `and_(restricted, participant_email == me)` back. Non-admin users now see a case if it is open, or if it is restricted and they are a participant.

**Test gap:** The existing tests passed with the bug in place, so nothing covers this filter. I didn't add a test because you only asked for the fix. I can add one that builds a restricted case with and without the user as a participant, if you want.

Nothing is committed. The working tree has this fix, the earlier incident permission fix, and the new `tests/incident/` test.

----- next turn -----



----- next turn -----

The POST handler stores the raw payload unmasked and commits it. A separate background processor masks it later, so the unmasked payload is written to the database. I only read code and changed nothing.

## Trace

**1. Ingest** — `create_signal_instance` in `signal/views.py:70`, rate-limited to 1000/minute.
- It resolves the project, then the signal definition. The lookup order is external id or variant from `raw`, then the project's default definition, then a 404.
- It calls `signal_service.create_instance` and then `db_session.commit()`. A duplicate id returns 409.
- It never calls the processing flow. The response is the stored instance, and `background_tasks` is accepted but unused.
- This route has no `PermissionsDependency`, which fits the earlier review. It is an open reporting endpoint.

**2. Persist** — `signal/service.py:650`, `create_instance`.
- It copies `signal_instance_in.raw`, drops `oncall_service`, and round-trips it through JSON to serialise dates. That copy becomes the `raw` column.
- There is no redaction here. A UUID `raw["id"]` becomes the primary key, and a non-UUID id gives a 400.

**3. Pick up** — the processing loop runs later.
- `process_organization_signals` in `signal/flows.py:406` loads the unprocessed instance ids, meaning `filter_action IS NULL`, and `process_signal_batch` (`:385`) calls the flow for each. `cli.py:~1004` does the same in the scheduler loop.
- Each instance gets its own commit, and a failure rolls back and logs.

**4. Flow** — `signal_instance_create_flow`, `signal/flows.py:46`. It runs these steps in order:
- **Masking:** `signal_instance.raw = redact_raw(signal_instance.raw)` at `:60`, before entities are extracted.
- **Entities:** it extracts entities from the masked payload, assigns them to the instance and commits.
- **Filtering:** `signal_service.filter_signal` (`service.py:866`) applies snooze, then dedup rules, then a default dedup window. If a filter matches, the instance gets `filter_action` set (snooze or deduplicate), the case's Slack message may be updated if there is a conversation, and the flow returns. This is the filtered-out path.
- **Early returns:** canary instances, and signals with `create_case` off, are stored and returned without a case.
- **Case creation:** it resolves case type, priority, oncall assignee and conversation target, building a `CaseCreate` with `Visibility.open`. It then calls `case_service.create`, links `signal_instance.case`, commits, runs `case_new_create_flow`, engages the signal identity if there are engagements and entities, and runs any signal workflows.

## Masking details

- **Function:** `redact_raw` in `signal/redaction.py`. It is called from `signal/flows.py:60`, and nowhere else in the source.
- **Behavior:** it returns a copy with the value of every matching key replaced by `"[REDACTED]"`.
  - Keys match case-insensitively, at any depth, inside dicts and lists.
  - Only values under matching keys are masked. Key names stay, and non-dict or list values pass through.
  - A matching key whose value is a nested dict or list is replaced wholesale.
- **Default keys:** `password`, `secret`, `api_key`, `session_token`, `authorization`. They come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which can be overridden with an env var holding a comma-separated list.
- **Exact match only:** `client_secret`, `apiKey`, `access_token` and `Set-Cookie` are not masked by default, because matching is on the whole key name.

## Is the unmasked payload written to the database?

Yes, in two ways:
- **At ingest, always.** Step 2 commits the full raw payload, including secrets, before any redaction. It stays that way until the processor reaches the instance, which normally takes up to about a minute (`LOOP_DELAY = 60`). If the processor never runs, or errors out for that instance, it stays unmasked permanently.
- **Possibly in history.** Anything that snapshots the table, such as backups, replicas or WAL, can hold the original value after masking. I did not check for audit tables or triggers.

Masking only reaches the DB on a later commit. `process_signal_batch` commits after each instance, so that is the usual path. If the flow raises before that commit, the rollback discards the masking too.

Unprocessed instances are also readable without masking through `GET /signals/instances`, which uses `search_filter_sort_paginate` and the read schema. I haven't checked whether `SignalInstanceRead` exposes `raw`.

Two other things I noticed:
- In `create_signal_instance` (`views.py`), `external_id` and `variant` are only assigned when `signal_instance_in.signal` is falsy. If a signal is supplied, `signal_definition` is never set, so the following `if not signal_definition` check would raise `NameError`. I didn't test this.
- The scheduler-oriented `create_signal_instance` in `flows.py:231` also stores `raw=signal_instance_data` unmasked, with the same later masking.

I'd fix this by calling `redact_raw` in `signal_service.create_instance` (or in the view) before the first commit. I haven't made that change.

----- next turn -----

Entity extraction now creates an entity for every JSONPath match again, and the `tests/entity` suite passes (11 tests).

**Cause:** commit `beb60cc4`, "perf(entity): stop at the first JSONPath match" (Sam Ortega, 2025-09-02). It changed `find_entities` in `src/dispatch/entity/service.py` to `matches = jpath.find(signal_instance.raw)[:1]`. That cut the list of matches to one, so only the first matching field became an entity.

**Fix:** I removed the `[:1]` slice and the comment that justified it, which restores the original line. I didn't change any tests, and nothing is committed.

The "perf" commit saved almost nothing. `jpath.find` still evaluates every match, and the slice only skipped creating the extra `EntityCreate` objects, which are the entities the tests expect.

----- next turn -----

Masked values no longer become entities. The new test fails without the fix and passes with it, and `tests/entity` and `tests/signal` pass.

**Why unrelated instances were grouped:** the flow masks the raw payload first (`redact_raw` at `signal/flows.py:60`). Then `find_entities` runs a JSONPath such as `session_token` over it, and every instance now holds the identical string `"[REDACTED]"` at that path. `get_by_value_or_create` reuses a single `[REDACTED]` entity per project and entity type. The dedup filter on that entity type then sees every instance as sharing the same entity and puts them in one case.

**Fix:** in `find_entities` in `src/dispatch/entity/service.py`, a match is skipped when its value equals `MASK`, which I import from `signal/redaction.py`. `find_entities` is the only place entities are extracted from a payload. It is called from the signal flow and from `entity_type/service.py` (re-extraction when an entity type is created or updated), so both paths are covered. The masking itself is unchanged.

**Test:** `tests/entity/test_entity_masked_values.py` is a new file; no existing test was edited. It masks a payload containing `session_token` and a nested `password`, plus an unmasked `user` field. It asserts that only the `user` value becomes an entity.

**Caveats:**
- The diff for `entity/service.py` also contains the `[:1]` removal from the earlier fix. Nothing is committed.
- Instances already processed before this fix may have been linked to a `[REDACTED]` entity, and those links were not cleaned up. Existing cases that were wrongly grouped are not split.
- Entity types whose JSONPath points at a field that is genuinely always masked will now produce no entities.
- A signal instance that has not been processed yet still has an unmasked `raw` in the DB, as I noted earlier. If an entity type is created or updated in that window, re-extraction in `entity_type/service.py` would create entities from the real secret. Masking at ingest would close that gap.

----- next turn -----

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