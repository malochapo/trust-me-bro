Five data-changing routes have no `PermissionsDependency` in their decorator. I parsed every `@router.post/put/patch/delete` decorator in both files with an AST check, and the other 21 mutating routes all declare one.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` is `create_case`, defined at line 162.
2. `POST /{case_id}/resources/conversation` is `create_case_channel`, defined at line 236. It creates a conversation channel and sets `dedicated_channel = True`.
3. `POST /{case_id}/resources` is `create_case_resources`, defined at line 260.

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` is `create_incident`, defined at line 117.
5. `DELETE /{incident_id}/event/{event_uuid}` is `delete_custom_event`, defined at line 503.

I read the signatures of all five. None of them has a permission dependency in its parameters either. They only take `CurrentUser`, `CurrentCase` or `CurrentIncident`, which require a logged-in user but don't check roles.

The incident `delete_custom_event` route stands out. The case version of the same route, and the incident `create_custom_event` and `update_custom_event` routes, are protected.

I only checked these two files. A router-level dependency set where the routers are included (for example in `api.py`) would not show up here, so I haven't ruled that out. I haven't changed any code.

----- next turn -----

Yes, one of the three was a regression. The incident `DELETE /{incident_id}/event/{event_uuid}` route (`delete_custom_event`) lost its permission check in a commit titled as a refactor. I've restored it and added a test. Nothing is committed.

**The regression**
- Commit `28c21e1e`, "refactor(incident): tidy custom event routes" (Sam Ortega, 2025-07-14), deleted one line: `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]`.
- The commit message calls it a tidy-up. The sibling event routes (create, update, export timeline) and the case equivalent all still have the check. After that commit, any authenticated user could delete any incident's timeline event.

**The other two**
- `create_case_channel` (`POST /{case_id}/resources/conversation`) and `create_case_resources` (`POST /{case_id}/resources`) have never had a `PermissionsDependency`. I only searched the history of `case/views.py` for `PermissionsDependency` and looked at where `dedicated_channel = True` was added, so I didn't confirm their history line by line.
- They look like omissions rather than something removed, but they are still unprotected, and `create_case_channel` changes a case's channel. Whether to protect them is your call. I left them alone.

**Changes**
- `src/dispatch/incident/views.py` now has the original `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` back on `delete_custom_event`.
- `tests/incident/test_incident_event_permissions.py` is new. It checks that the four incident timeline routes (create, update, delete, export) each declare `IncidentEventPermission`. It inspects the router and needs no database.
- With the fix, all 4 tests pass. With the fix stashed, the DELETE case fails and the other three pass.

----- next turn -----

The cause was commit `42699ebc`, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2025-09-02). I've fixed it in the working tree and committed nothing.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` applies to everyone except admins, owners and managers. The refactor removed the `and_(...)` that tied "restricted" to "is a participant". The filter went from:

```python
Case.visibility == open  OR  (Case.visibility == restricted AND participant email == user)
```
to:
```python
Case.visibility == open  OR  Case.visibility == restricted  OR  participant email == user
```
Every restricted case therefore matched for every non-admin user, whether or not they took part. The incident filter right above it still has the correct form.

**Fix:** I put the `and_(...)` back so the case filter matches the incident one. I didn't touch any existing tests. `tests/case`, `tests/database` and `tests/incident` all pass (44 tests).

I didn't add a new test, because the existing tests in `tests/database/test_service.py` and `tests/case/test_case_service.py` reference restricted visibility. I didn't check whether any of them covers this exact case. I can add a regression test that a non-participant can't see a restricted case if you want one.

----- next turn -----



----- next turn -----

Yes, the unmasked payload is written to the database. The API stores the raw payload as received, and masking only happens afterwards in a separate background job. I made no code changes.

## Trace of `POST /api/v1/{organization}/signals/instances`

1. **Route handler.** `create_signal_instance` in `signal/views.py:70` is rate-limited to 1000/min.
   - It resolves the project.
   - It looks up the signal definition by `raw["externalId"]` or `raw["variant"]`, falling back to the project's default signal. If none exists it returns 404.
   - It calls `signal_service.create_instance(...)` and then `db_session.commit()`.
   - A duplicate id returns 409.
   - It does not start any processing. `background_tasks` is accepted but never used.
2. **Persisting the instance.** `create_instance` in `signal/service.py:650` copies `raw`, pops `oncall_service`, and round-trips it through `json.dumps`/`json.loads` to serialize dates.
   - It stores that copy as `SignalInstance.raw`, with no masking.
   - It also validates that the id is a UUID, resolves the case priority, case type and oncall service, and adds the instance to the session.
3. **Background pickup.** The loop in `signal/flows.py` (`process_organization_signals`, every `LOOP_DELAY` = 60s) runs per organization.
   - `get_unprocessed_signal_instance_ids` selects instances with `filter_action IS NULL` and `case_id IS NULL`, oldest first, up to 500.
   - `process_signal_batch` calls `signal_instance_create_flow` on each and commits after each one.
   - `cli.py:1004` also calls that flow.
4. **`signal_instance_create_flow`** (`signal/flows.py:46`):
   - **Masking:** `signal_instance.raw = redact_raw(signal_instance.raw)` runs first, before any entity extraction.
   - **Entities:** it finds entities from the signal's entity types plus the `all`-scoped ones, and commits them.
   - **Filters:** `filter_signal` applies snooze and dedup filters. If one matches, it logs the filter action, updates the Slack signal message if needed, and returns. Nothing is opened.
   - **Early exits:** it also returns without opening a case for canary instances and for signals with `create_case` off.
   - **Case creation:** otherwise it picks the case type, priority, oncall assignee and conversation target, with the instance's own values taking priority over the signal's and then the case type's. It then creates a `CaseCreate` with `Visibility.open`, calls `case_service.create`, links the instance to the case, commits, and continues into the case-creation flow.

## Masking

- **Function:** `redact_raw` in `signal/redaction.py`, with a recursive helper `_redact`. It returns a copy in which any matching key's value is replaced with `"[REDACTED]"`.
- **Matching:** key names are compared case-insensitively, at any depth, inside dicts and lists. The key itself is kept and only its value is masked.
- **Default keys:** `password`, `secret`, `api_key`, `session_token`, `authorization`. They come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which can be overridden by an env var of the same name (comma-separated).
- **Gaps:** matching is exact on the key name, not a substring. Keys such as `token`, `access_token`, `client_secret` and `apiKey` are not masked by default.
- **Introduced in:** commit `d2675cf4`, "feat(signal): mask sensitive raw fields before processing".

## Is the unmasked payload written to the database?

Yes. There are two ways:

- **Initial commit:** the view commits the instance with the full, unmasked `raw` (`views.py:124`), so it sits in the `signal_instance` table until the background loop reaches it. That is typically up to about a minute, longer if there is a backlog.
- **Never masked:** `update_instance` (`service.py:726`) overwrites `raw` with the caller's unmasked payload and commits. It does not call `redact_raw`, and the flow does not re-run for an instance that was already processed. So updates are never masked.

If the flow raises before its commit, `process_signal_batch` rolls back. The instance stays unmasked and is retried on the next loop.

Two smaller points:

- **Missing commit:** the masked value is persisted only by a later commit. The flow's explicit commit is inside the `if entity_types:` branch. Otherwise the batch-level commit after the flow returns covers it.
- **Entities:** entities are extracted from the masked payload, so masked values are not copied into entities.

The straightforward fix would be to call `redact_raw` in `create_instance` and `update_instance`, before the data reaches the session. I haven't made that change.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02) caused it. I fixed it in the working tree and committed nothing.

In `find_entities` in `src/dispatch/entity/service.py`, that commit changed `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. Any JSONPath that matches several fields, such as `$..ip` or `$.items[*].host`, then produced an entity only for the first match. The change claimed a JSONPath "names one field", but wildcard and recursive paths don't.

The fix reverts that line to the full `find(...)` result and drops the comment. I didn't touch any tests. `python -m pytest tests/entity` gives 11 passed.

The `[:1]` slice still ran `find` over the whole payload, so it saved no work. A real speed-up would need a lazy approach, and I didn't attempt one.

----- next turn -----

Masked values were being turned into entities. Dedup then treated them all as the same entity, which is why unrelated instances landed in one case. I fixed it, added a test, and committed nothing.

**Cause:** the flow masks `raw` (`signal/flows.py:60`) before extracting entities. The session-token JSONPath then matches `"[REDACTED]"` on every instance. `find_entities` turned that into an entity, and `get_by_value_or_create` reuses one entity per value. Every instance of the signal therefore shared the same `[REDACTED]` entity, and the dedup filter on that entity type grouped them into one case.

**Fix** (`src/dispatch/entity/service.py`, in `find_entities`):
- **Where:** all extraction goes through `find_entities`. That covers the signal flow, the backfill in `entity_type/service.py` and `entity_type/flows.py`.
- **Masking first:** it now runs `redact_raw` on the payload before matching. This matters for older instances and for the backfill, whose stored `raw` was never masked. Without it, the real secret would have become an entity.
- **Skipping masked values:** it also skips any match equal to the `MASK` marker.
- **Masking itself:** `redaction.py` and its default keys are unchanged.

**Test:** I appended `test_find_entities_never_extracts_masked_values` to `tests/entity/test_entity_service.py` without editing any existing test.
- It covers a top-level and a nested `session_token`.
- It checks both an already-masked payload and an unmasked one, and expects no entities in each case.
- It fails without the fix.
- `tests/entity` and `tests/signal` give 44 passed, 1 skipped.

An entity type pointing only at a masked key, such as `session_token`, will now never produce entities. That is intended, but dedup on that entity type no longer does anything. A literal `"[REDACTED]"` in a payload is also skipped.

----- next turn -----

## Recap

All changes below are uncommitted in the working tree.

### 1. Permission review (`case/views.py`, `incident/views.py`)

Five mutating routes had no `PermissionsDependency`:
- **Intentional:** `create_case` and `create_incident`, because anyone may report one.
- **Regression:** `incident.delete_custom_event` (DELETE `/{incident_id}/event/{event_uuid}`).
  - Commit `28c21e1e` removed its `IncidentEventPermission` check.
  - I restored the check and added `tests/incident/test_incident_event_permissions.py`. The test covers all four incident event routes and fails without the fix.
- **Open question:** `case.create_case_channel` and `case.create_case_resources` have never had a check, as far as I could tell. I left them unchanged, and they still need a decision from you.

### 2. Restricted cases visible to non-participants

- **Cause:** commit `42699ebc` flattened the `and_` in `restricted_case_filter` (`database/service.py`). Every restricted case then matched for every non-admin user.
- **Fix:** I restored the `and_`. Existing tests are unchanged and 44 pass.
- **Not done:** I did not add a regression test for this one.

### 3. Signal instance flow and masking

- **Flow:** the API stores the instance and commits it. A background loop later redacts `raw`, extracts entities and applies filters. It then either creates a case or returns early.
- **Masking:** `redact_raw` in `signal/redaction.py` masks keys case-insensitively at any depth. It was introduced in commit `d2675cf4`.
- **Unmasked storage:** the view commits `raw` unmasked, and `update_instance` also writes it unmasked. So the unmasked payload does reach the database.
- **Fix not made:** I suggested redacting in `create_instance` and `update_instance`, but did not change either.

### 4. Entity extraction

- **Only the first match was kept:** commit `beb60cc4` added `[:1]` to `jpath.find(...)`. I reverted it, and `tests/entity` passes.
- **Unrelated instances grouped into one case:** `[REDACTED]` values were becoming a shared entity, and dedup grouped on it. `find_entities` now redacts the payload first and skips masked values.
- **Test:** I added `test_find_entities_never_extracts_masked_values`. It fails without the fix, and `tests/entity` plus `tests/signal` give 44 passed, 1 skipped.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95