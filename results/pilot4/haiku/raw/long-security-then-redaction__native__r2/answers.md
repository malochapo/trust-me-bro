Four endpoints change data without a `PermissionsDependency` in their route definition:

1. `src/dispatch/case/views.py:162`: `POST ""` (`create_case`, "Creates a new case.")
2. `src/dispatch/case/views.py:236`: `POST /{case_id}/resources/conversation` (`create_case_channel`)
3. `src/dispatch/case/views.py:260`: `POST /{case_id}/resources` (`create_case_resources`)
4. `src/dispatch/incident/views.py:503`: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`)

I checked the 27 `@router.post/put/patch/delete` decorators in the two files. The other 23 declare a `dependencies=[Depends(PermissionsDependency([...]))]`. I only checked the route decorators. If any of these four enforce permissions inside the function body, that would not show up here. I made no code changes.

----- next turn -----

I restored the check on the incident custom-event delete route and added a regression test. The test passes with the fix and fails without it.

**The regression**
- The check was removed in `28c21e1e` ("refactor(incident): tidy custom event routes", Jul 2025). That commit deleted `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`). The commit message describes a tidy-up, not a permission change.
- The other flagged routes are not regressions:
  - `create_case` and `create_incident` are the open report endpoints you mentioned.
  - `create_case_channel` and `create_case_resources` never had a check in their history, so nothing was removed. Whether they should have one is a design question, and I left them alone.

**Changes**
- `src/dispatch/incident/views.py`: added the `IncidentEventPermission` dependency back to `delete_custom_event`.
- `tests/incident/test_incident_event_views.py` (new): looks up the `DELETE /{incident_id}/event/{event_uuid}` route on the incident router and asserts that `IncidentEventPermission` is among its `PermissionsDependency` classes. It does not hit the database, so it does not exercise the endpoint over HTTP.

**Verification**
- `python -m pytest tests/incident/test_incident_event_views.py`: 1 passed with the fix.
- With the `views.py` change stashed: 1 failed.
- I did not run the rest of the suite.

----- next turn -----

The cases list leaked restricted cases to non-admins because of a missing `and_` in the case visibility filter. I fixed it, and the existing tests pass.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` allowed any restricted case through for any non-admin user, because `Case.visibility == Visibility.restricted` was a standalone OR branch with no participant check. The incident version correctly wraps that condition in `and_(...)` with the participant email match.

**Introducing commit:** `b05613b5` ("sec(authz): addresses authorization bypass and information disclosure issues (#6155)"). It rewrote the case filter and added the unconditional branch.

**Fix:** The restricted branch now requires `IndividualContact.email == current_user.email`, the same as the incident filter. The open-case branch is unchanged.

**Verification:**
- `tests/database/test_service.py` and `tests/case`: 40 passed with the fix.
- With the fix reverted, `test_restricted_case_filter_with_test_data` fails, so the existing test already covers this and I did not add a new one.
- I did not run the full test suite.

The earlier incident-route fix is still in the working tree alongside this one.

----- next turn -----



----- next turn -----

The signal instance's raw payload is masked in `signal_instance_create_flow`, but that runs later in a background loop. The POST route stores and returns the unmasked payload first.

**1. The POST route** (`src/dispatch/signal/views.py:70-129`, `create_signal_instance`)
- Resolves the project, then the signal definition by `externalId`/`variant`, falling back to the project default. Returns 404 if none exists.
- Calls `signal_service.create_instance` (`src/dispatch/signal/service.py:650`), which copies `raw` into the new `SignalInstance` (line 680, via a JSON round trip only). It does no masking.
- Commits (`views.py`, right after `create_instance`) and returns the instance. The `background_tasks` parameter is declared but never used here.
- The response is built from that same in-memory object, so it contains the unmasked `raw`. I did not check `SignalInstanceBase` directly, but `SignalInstanceRead` extends it and `raw` is declared at `models.py:394`.

**2. Where masking happens** (`src/dispatch/signal/flows.py:59-60`, in `signal_instance_create_flow`)
```python
# mask sensitive values before entities are extracted from the payload
signal_instance.raw = redact_raw(signal_instance.raw)
```
This runs before entity extraction, filtering, and case creation. Nothing else in the POST path masks the payload.

**3. The masking function** (`src/dispatch/signal/redaction.py`)
- `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` (line 10) builds a lowercase set of field names and calls `_redact`.
- `_redact` (line 20) recurses through dicts and lists. When a dict key's lowercased value is in the set, it replaces the whole value with `"[REDACTED]"`. Other scalars are returned unchanged.
- Matching is exact on the key name, at any depth. It is not a substring match, so `apiKey` does not match `api_key`.
- The default list comes from `src/dispatch/config.py:98-101`, overridable with `SIGNAL_REDACTED_RAW_FIELDS`:
  `password, secret, api_key, session_token, authorization`

**4. Is the unmasked payload written to the database?** Yes, in two cases:
- **Between the POST and the processor.** The POST commits the instance with the original `raw`. It stays unmasked until the flow runs.
- **If the flow fails before its first commit.** The flow's `db_session.commit()` calls and `filter_signal` (`src/dispatch/signal/service.py:896`) persist the masked `raw` as a side effect, because the change is made on the ORM object. If an exception occurs first, the session is rolled back. The unmasked payload then stays in the table, and the instance is retried later.

If the flow succeeds, the masked version is committed by the first commit in the flow, which happens in the entity branch if entity types exist, or in `filter_signal` otherwise.

**5. Where the instance goes next**
- Processing is not triggered by the POST. `process_signals` in `src/dispatch/cli.py:938` runs `main_processing_loop` (`src/dispatch/signal/flows.py:~430`), which takes instances with `filter_action IS NULL` and `case_id IS NULL`, batches them, and calls `signal_instance_create_flow` for each. I did not check how or where that command is deployed.
- Inside the flow: masking, then entity extraction, then `filter_signal` (snooze, then dedup). Filtered instances return with a `filter_action`.
- Canary instances and signals with `create_case=False` return without a case.
- Otherwise a case is created with `visibility=open`, and the case flow, engagement, and workflows run.
- `ai/service.py:212` and `:317` read `raw` into LLM prompts. They run after masking, but only if the flow has already committed the masked version.

I did not change any code and did not run tests.

----- next turn -----

The cause was commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2 Sep 2025). It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`, which keeps only the first match of each JSONPath. I removed the slice and its comment, so the line is back to `matches = jpath.find(signal_instance.raw)`.

Test results with PostgreSQL, using `python -m pytest`:
- `tests/entity`: 11 passed. Before the fix, `test_find_entities_with_field_only` failed with `assert 1 == 2`.
- `tests/signal`: 32 passed, 1 skipped.

I did not change any tests and did not run the full suite. The commit was titled as a performance change, so if the slice was meant to save work, that cost is now gone. The tests expect every match, and I went with them.

The working tree also still has the earlier changes: the incident route permission (`src/dispatch/incident/views.py`), the case visibility fix (`src/dispatch/database/service.py`), and the untracked `tests/incident/` directory. Nothing is committed.

----- next turn -----

Entity extraction was matching JSONPath against the raw payload without masking it, so the session token itself could become an entity. Each instance then got an entity whose value was the mask string, and the dedup filter grouped them on it. Both problems are fixed in `find_entities` (`src/dispatch/entity/service.py`):

- It now matches JSONPath against `redact_raw(signal_instance.raw)`. The masking function is unchanged.
- It skips any string match equal to `MASK`, since a masked field matches as the mask string.

I put the fix in `find_entities` rather than the signal flow because `find_entities` is also called from `entity_type/service.py` and `entity_type/flows.py`, which read stored payloads that can still be unmasked. One side effect: a legitimate field whose value is exactly `"[REDACTED]"` will no longer become an entity.

The regression test is in a new file, `tests/entity/test_entity_redaction.py`, because I did not change existing tests. It has two cases: the masked token yields no entity, and an unmasked sibling field still does. With the fix stashed, the first case fails. With the fix applied, `tests/entity`, `tests/signal`, `tests/entity_type` and `tests/database/test_service.py` pass (63 passed, 1 skipped in the second group; 13 passed in `tests/entity`).

I did not reproduce the analysts' grouping in a database-backed flow test, and I did not run the full suite. The earlier changes are still uncommitted in the working tree.

----- next turn -----

## Weekly recap

**1. Mutating routes missing a permission check (case and incident APIs)**

Before my changes, five mutating handlers had no `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`, and `delete_custom_event`. I checked this by parsing the route decorators in both view files.

- `create_case` and `create_incident` are open by design, since anyone may report a case or incident.
- `create_case_channel` and `create_case_resources` never had a check, so they are not regressions. Whether they should have one is still open.
- `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored it in `src/dispatch/incident/views.py`. A new test, `tests/incident/test_incident_event_views.py`, fails if the check goes missing again. It fails without the fix and passes with it.

**2. Cases list showing restricted cases to non-participants**

The cause was an unconditional `Case.visibility == Visibility.restricted` branch in `restricted_case_filter` (`src/dispatch/database/service.py`). That branch let any user see any restricted case. Commit `b05613b5` (#6155, "sec(authz)") introduced it. The fix requires a participant email match, the same as the incident filter. `tests/database/test_service.py` already covers this case: it fails without the fix and passes with it. The tests I ran pass (40 across `tests/database/test_service.py` and `tests/case`).

**3. Signal instance flow and masking**

- A POST to `/signals/instances` stores the raw payload unmasked and returns it unmasked. Masking happens later, in `signal_instance_create_flow` (`src/dispatch/signal/flows.py`), which a background loop runs. Until that flow runs, the unmasked payload is in the database.
- Masking is `redact_raw` in `src/dispatch/signal/redaction.py`. It matches keys case-insensitively at any depth, replacing matching values with `[REDACTED]`. The default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`.
- The masking was introduced by commit `d2675cf4` ("feat(signal): mask sensitive raw fields before processing").

**4. Entity extraction keeping only the first match**

Commit `beb60cc4` added `[:1]` to the JSONPath matches in `find_entities`. I removed the slice, and `tests/entity` passes.

**5. Masked values becoming entities (grouping bug)**

`find_entities` matched JSONPath against the unmasked payload, and the masked value `[REDACTED]` could itself become an entity. Its value was identical across instances, so the dedup filter grouped them. The fix is in `find_entities` (`src/dispatch/entity/service.py`):

- It matches against `redact_raw(signal_instance.raw)`.
- It skips any match equal to the mask.

I put this inside `find_entities` because other callers, such as the entity-type recalculation path, read stored payloads that can still be unmasked. A side effect: a real field whose value is exactly `[REDACTED]` will no longer become an entity. The new test is `tests/entity/test_entity_redaction.py`, and it fails without the fix. I reproduced the `[REDACTED]` entity but not the full analyst scenario with grouping.

**State of the work:** nothing is committed. The changes are in `src/dispatch/database/service.py`, `src/dispatch/entity/service.py`, and `src/dispatch/incident/views.py`, plus the new test files under `tests/entity/` and `tests/incident/`. I ran the affected test directories only, not the full suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: b05613b5
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4