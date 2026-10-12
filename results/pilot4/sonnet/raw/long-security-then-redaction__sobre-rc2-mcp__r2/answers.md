Five data-changing routes declare no `PermissionsDependency` in their route definition. I checked this by reading the route decorators in both files.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` is `create_case` (line 162).
2. `POST /{case_id}/resources/conversation` is `create_case_channel` (line 236).
3. `POST /{case_id}/resources` is `create_case_resources` (line 260).

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` is `create_incident` (line 117).
5. `DELETE /{incident_id}/event/{event_uuid}` is `delete_custom_event` (line 503).

- **Delete route:** The same delete route in the case API (`DELETE` on a case's custom event) does declare `CaseEventPermission`. Only the incident version is missing it.
- **Create routes:** I only checked the route definitions. Dispatch may apply authentication or other controls elsewhere, such as router-level dependencies or middleware. I did not check for those, so this list covers only what the route definitions declare.

Every other POST, PUT, PATCH and DELETE route in the two files declares a `PermissionsDependency`. The two GET routes `generate_tactical_report` and `generate_summary` also declare one, and they don't change data in any case.

----- next turn -----

Yes, one of the three was a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event` in `src/dispatch/incident/views.py`). I've restored its check and added a test. I haven't committed anything.

**The regression:** commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, 2025-07-14) removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from that route. The commit message describes a tidy-up, but the diff is just that deletion. Because of it, any caller who gets past authentication could delete incident timeline events without the event permission. The matching case route still requires `CaseEventPermission`.

**The other two were never protected:** `create_case_channel` and `create_case_resources` have had no permission check since they were added, in `f08a22b3` and `ced74f33`. That makes them an original design gap rather than a regression, so I left them alone. They're probably worth reviewing separately, because they trigger resource creation for an existing case.

**The fix:** I put the `IncidentEventPermission` dependency back on the route in `src/dispatch/incident/views.py`.

**The test:** `tests/incident/test_incident_route_permissions.py` looks up that route and asserts that `IncidentEventPermission` is among its dependencies. I ran it both ways with `python -m pytest`:
- With the fix, it passes.
- With the fix stashed, it fails.

My first version of the test had a typo (`permission_classes` instead of `permissions_classes`) and failed in both states. That's fixed, and the runs above are from the corrected version.

----- next turn -----

The cause was a refactor that flattened the filter condition in `restricted_case_filter`. That commit is `42699ebc`, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2025-09-02). I've fixed it in `src/dispatch/database/service.py` and haven't committed anything.

**Cause:** The filter is meant to show non-admin users open cases, plus restricted cases they take part in. The refactor turned this:

```python
Case.visibility == Visibility.open,
and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email),
```

into three separate `or_` branches:

```python
Case.visibility == Visibility.open,
Case.visibility == Visibility.restricted,
IndividualContact.email == current_user.email,
```

The middle branch matches every restricted case for every user, regardless of participation. That is why the security team member sees restricted cases they aren't part of. `restricted_incident_filter` still has the `and_`, so incidents weren't affected.

**Fix:** I restored the `and_(...)` around the restricted-visibility and email checks, so the case filter matches the incident one again. I didn't touch any existing tests.

**Tests:** The full suite gives 361 passed, 7 failed and 4 skipped. The 7 failures are in `tests/ai/test_ai_service.py` (6) and `tests/entity/test_entity_service.py::test_find_entities_with_field_only` (1). I ran `tests/ai` and `tests/entity` with my changes stashed and the same tests fail, so they aren't caused by this change.

I didn't add a regression test for this filter. I can add one that checks a non-participant doesn't see a restricted case, if you want.

----- next turn -----



----- next turn -----

**Short answer:** the masking is `redact_raw()` in `src/dispatch/signal/redaction.py`, and the unmasked payload is written to the database first. The API request stores it, and masking only happens later, in the worker that processes the instance.

## Trace

1. **API request.** `create_signal_instance` (`src/dispatch/signal/views.py:70`) is the POST `/instances` handler.
   - It resolves the project.
   - It finds the signal definition by `externalId` or `variant`, then falls back to the project's default definition.
   - If no definition exists, it returns 404.
   - It then calls `signal_service.create_instance` and `db_session.commit()`.
   - A duplicate id raises `IntegrityError`, which becomes a 409.
   - The handler takes `background_tasks` but never uses it, so it does no processing itself.

2. **Storing the instance.** `signal_service.create_instance` (`src/dispatch/signal/service.py:650`) builds the `SignalInstance`.
   - It copies `signal_instance_in.raw`, drops `oncall_service`, and round-trips the copy through JSON.
   - It does no masking.
   - It sets `raw=` from that copy and calls `db_session.add(...)` (line 722).

3. **Worker pickup.** Processing happens in a separate worker.
   - `process_organization_signals` and `process_signal_batch` are in `signal/flows.py:~383`.
   - The CLI loop is at `cli.py:~1004`.
   - Both select instances where `filter_action IS NULL` and `case_id IS NULL`, then call `signal_instance_create_flow`.

4. **`signal_instance_create_flow`** (`signal/flows.py:46`):
   - **Masking.** It runs `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60), before entity extraction.
   - **Entities.** It extracts entities.
   - **Filtering.** It calls `signal_service.filter_signal`. If a filter acts (deduplicate or snooze), it returns early. It may update the Slack message for an existing case.
   - **Early exits.** Canary signals, and signals with `create_case` off, are stored and returned without a case.
   - **Case creation.** Otherwise it resolves case type, priority, oncall assignee and conversation target, and calls `case_service.create`. That case is open visibility, and it attaches the case and continues into the case creation flow.

## Masking details

- **Function:** `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)`, which calls the recursive `_redact`. It was added in commit `d2675cf4`.
- **Default keys** (`src/dispatch/config.py:98`): `password`, `secret`, `api_key`, `session_token`, `authorization`. The `SIGNAL_REDACTED_RAW_FIELDS` environment variable overrides the list, as comma-separated names.
- **Matching rules:**
  - Keys match case-insensitively and by exact name, not substring. `db_password` or `apiKey` would not be masked.
  - It matches at any depth, inside dicts and lists.
  - A matching key's whole value is replaced with `"[REDACTED]"`.
  - It returns a copy, and the flow assigns that copy back to `raw`.

## Is the unmasked payload ever written to the database?

Yes. In the POST handler, `create_instance` stores the raw payload as received and `db_session.commit()` persists it.

- **Window.** The unmasked payload sits in `signal_instance.raw` until the worker picks the instance up. It is only overwritten in the worker's later transaction, which commits after each instance in `process_signal_batch` and the CLI loop.
- **If processing fails.** `signal_instance_create_flow` can raise after masking, and the batch loop then rolls back. The masked value is lost with that rollback, so the instance stays unmasked and gets retried.
- **Other readers.** Anything that reads the row before processing sees the secrets. That includes `GET /signals/instances` and the UI.
- **Unprocessed instances.** Instances never picked up by the worker keep their secrets.
- **Not covered by the masking.** `update_instance` (`service.py:~727`) was not inspected, so I can't say whether it re-stores raw data unmasked.
- **Elsewhere in the payload.** `redact_raw` only changes `raw`. Other fields on the instance, and the API request itself, are not masked. I didn't check whether request logging captures the body.

Moving the `redact_raw` call into `create_instance`, or into the POST handler before the commit, would close the window. I haven't changed any code.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02) caused this, and I've fixed it.

It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`. That kept only the first match for each entity type, so any JSONPath that matches several fields produced one entity.

I reverted that line to `matches = jpath.find(signal_instance.raw)` and removed the comment the commit added. I didn't touch any tests. `python -m pytest tests/entity` now gives 11 passed, including `test_find_entities_with_field_only`, which was among the failures I'd seen earlier. I didn't re-run the full suite.

Nothing is committed.

----- next turn -----

Unrelated "Personal access token exposed" instances were grouped because every one of them produced the same entity, the literal string `[REDACTED]`. The fix and its test are in, and `tests/entity` passes (12 tests).

**Cause:**
- `signal_instance_create_flow` runs `redact_raw` before it extracts entities.
- `session_token` is one of the default masked keys, so the entity type's JSONPath then matches `"[REDACTED]"` in every instance.
- `find_entities` turned that into an entity with the same value each time.
- The deduplication filter on that entity type saw a shared entity and put unrelated instances into one case.

**Fix:** In `src/dispatch/entity/service.py`, `find_entities` now skips any match whose value equals `MASK` (imported from `dispatch.signal.redaction`). I left the masking itself unchanged. `find_entities` is the only place entities are extracted from a payload. Its callers are the signal flow, `entity_type/flows.py` and the entity-type update in `entity_type/service.py`, so all three are covered.

**Test:** `test_find_entities_skips_masked_values` in `tests/entity/test_entity_service.py` masks a payload with `redact_raw`. It checks that the `session_token` entity type and a `tokens[*].api_key` one yield nothing, while an unmasked field (`user.name`) still yields its entity. It fails with the fix removed, and I didn't change any existing test.

**Existing data:** Entities with the value `[REDACTED]` created before this fix are still in the database and may still link instances. Cases that were already grouped wrongly won't be split. I haven't touched either, and nothing is committed.

----- next turn -----

## Recap

**Investigation 1: permissions and visibility**
- Before my changes, five data-changing handlers had no `PermissionsDependency`. I re-derived this list from `HEAD` just now, since my earlier list was lost when the conversation was compacted. The five are `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, since anyone may report. `create_case_channel` and `create_case_resources` have never had a check, so they are a design gap worth a separate review.
- `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_route_permissions.py`, which fails if the check goes missing.
- Restricted cases appeared in the cases list because commit `42699ebc` flattened `restricted_case_filter` into three separate `or_` branches, so every restricted case matched for every user. I restored the `and_` wrapper.

**Investigation 2: signal pipeline**
- A signal instance is stored by the POST handler, then picked up by a worker. `signal_instance_create_flow` masks the payload with `redact_raw`, extracts entities, applies filters, and either opens a case or stops.
- The default masked keys are `password`, `secret`, `api_key`, `session_token` and `authorization`. Matching is by exact key name, case-insensitive, at any depth.
- The POST handler stores and commits the raw payload before masking, so the unmasked payload is written to the database.
- Commit `beb60cc4` made entity extraction keep only the first JSONPath match, and I reverted it.
- Masked values were becoming a shared `[REDACTED]` entity, so deduplication grouped unrelated instances into one case. `find_entities` now skips masked values, and `test_find_entities_skips_masked_values` covers it.

Nothing is committed. Seven tests in `tests/ai` and `tests/entity` were failing before my changes. The `tests/entity` one is fixed; the six in `tests/ai/test_ai_service.py` were not investigated, and I haven't re-run the full suite since.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4