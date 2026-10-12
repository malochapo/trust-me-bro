Five mutating routes across the two files have no `PermissionsDependency` in their route definition. I checked each route decorator in both files, and the ambiguous ones by reading the decorator and signature.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
3. `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

Every other POST, PUT, PATCH and DELETE route in the two files declares `dependencies=[Depends(PermissionsDependency([...]))]`.

- **Route-level scope:** I only looked at the route definitions, as you asked. A handler could still enforce authorization inside its body, or the router could be mounted with a router-level dependency elsewhere (for example in `api.py`). I didn't check either.
- **Not a mutating route:** `generate_tactical_report` (incident line 365) uses a GET decorator with single quotes, and it does declare a permission, so it isn't on the list.

Item 5 is the most notable gap. It is the only one of the four custom-event DELETE/PATCH/POST routes in the incident file that lacks `IncidentEventPermission`. The case version, `delete_custom_event` at `case/views.py:574`, does have it.

----- next turn -----

Yes, one of them is a regression: incident `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`). It's restored and covered by a test.

**Cause:** commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, 2025-07-14) removed one line from that route. The line was `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]`. The commit message calls it a tidy-up, but it dropped the authorization check.

**The other two case routes look intentional:** `create_case_channel` and `create_case_resources` have had no permission dependency since they were added (`ced74f33`, `f08a22b3`). I haven't asked whether that was a deliberate choice, so you may still want to check them. Neither is open to the public in the way reporting a case or incident is, since both act on an existing case.

**Changes (not committed):**
- `src/dispatch/incident/views.py`: put the `IncidentEventPermission` dependency back on that route.
- `tests/incident/test_incident_views_permissions.py` (new, plus an empty `tests/incident/__init__.py`): finds the route in the incident router and asserts `IncidentEventPermission` is among its permissions.

**Test result:** with the fix the test passes. With the `views.py` change stashed it fails, so it does catch the check going missing again. I only ran `tests/incident`, not the full suite.

----- next turn -----

The cases list was showing restricted cases to users who aren't participants, and I've fixed it in `src/dispatch/database/service.py`.

**Cause:** `restricted_case_filter` is applied to the cases list for every role except admin, owner and manager. Its visibility condition had lost the `and_(...)` grouping that tied "restricted" to "the user is a participant". It read as `open OR restricted OR participant-email-matches`. So every restricted case matched for every non-admin user, whether or not they took part.

**Commit:** `42699ebc`, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2025-09-02). It's the same author as the earlier regression, and again a "refactor" that changed behaviour. The incident version of the filter still has the correct grouping.

**Fix:** I restored the condition to `open OR (restricted AND participant-email-matches)`. I didn't touch any existing tests.

**Tests:** `tests/database` and `tests/case` pass. I ran `tests/ai` too because an earlier run hit failures there. Six `tests/ai` tests fail both with and without my changes, so they are unrelated. I ran only those three directories, not the full suite.

I didn't add a regression test for this one. Say if you'd like one that creates an open case, a restricted case with the user as participant, and a restricted case without them, and checks the filter output.

Both fixes (this one and the earlier incident permission) are uncommitted in the working tree.

----- next turn -----



----- next turn -----

**Short answer:** the masking is done by `redact_raw()` in `src/dispatch/signal/redaction.py`. It runs after the unmasked payload has already been committed to the database, so yes, the unmasked payload is written. I changed no code.

## Trace

1. **`POST /instances`** is `create_signal_instance` in `signal/views.py:70`.
   - It looks up the project.
   - It resolves the signal definition by `externalId` or `variant` in the raw payload, then falls back to the default definition, then returns 404.
   - It calls `signal_service.create_instance(...)` and `db_session.commit()`.
   - A duplicate id returns 409.
   - It returns the instance without running any processing. The `background_tasks` parameter is declared but never used.
2. **`create_instance`** (`signal/service.py:650`) builds the `SignalInstance` with `raw=json.loads(json.dumps(signal_instance_in.raw))`. This is a plain copy with no masking. It also sets the instance id from `raw["id"]`, which must be a UUID. It resolves the case priority, case type and oncall service, then calls `db_session.add`.
3. **Processing** happens later, in a separate worker. `cli.py:~985` selects instances where `filter_action IS NULL` and `case_id IS NULL`, up to 500, oldest first, and calls `signal_flows.signal_instance_create_flow` on each. `process_signal_batch` and `process_organization_signals` in `flows.py` do the same. Each instance is committed or rolled back separately.
4. **`signal_instance_create_flow`** (`signal/flows.py:46`) does the following in order:
   - It reloads the instance.
   - It masks the payload (`flows.py:60`).
   - It gathers entity types from the signal and from the `all` scope, then extracts entities with `entity_service.find_entities` and commits.
   - It runs `signal_service.filter_signal`: snooze first, then deduplication. If a filter action applied, it logs the action, updates the Slack signal message if a case already exists, and returns. The instance is filtered out.
   - Canary signals, and signals with `create_case` off, are stored and the flow returns.
   - Otherwise it resolves the case type, priority, oncall assignee and conversation target, then builds `CaseCreate` (visibility `open`, status `new`) and calls `case_service.create`. It links `signal_instance.case`, commits, and runs `case_flows.case_new_create_flow`. If the signal has engagements and entities, it also runs `engage_signal_identity`.

## Masking

- **Function:** `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` in `signal/redaction.py`. It recurses through `_redact`.
- **Behavior:** it returns a copy. It masks the values of matching keys with `"[REDACTED]"`. Key matching is case-insensitive and applies at any depth, inside dicts and lists. Values that are not dicts or lists pass through unchanged.
- **Default keys** (`SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`): `password`, `secret`, `api_key`, `session_token`, `authorization`. They can be overridden with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable, as a comma-separated list.
- **Limits:** it matches whole key names only. A key like `db_password` or `x-api-key` is not masked, and neither is a secret inside a string value.
- **Only caller:** `redact_raw` is called only at `flows.py:60`. Nothing in the API path calls it.

## Is the unmasked payload written to the database?

Yes. `create_instance` stores `raw` unmasked, and the view commits it before returning. The flow only masks it later, after a worker picks the instance up. That has several consequences:

- **Gap:** until the worker runs, the plaintext secrets are in `signal_instance.raw`. That includes the case where the worker is slow, backlogged, or not running.
- **Readable through the API:** `GET /instances` is not gated by any redaction, so it returns the unmasked payload during that window.
- **Unprocessed rows stay unmasked:** instances are only picked up while `filter_action` and `case_id` are both null. The batch is capped at 500 per cycle. Any row that raised an exception in the flow is rolled back. That includes the masking assignment, so the row keeps its plaintext and gets retried.
- **Outside the flow:** instances that never enter this flow are never masked. For example, `signal_service.create_signal_instance` (`service.py:162`) has no masking either.
- **Write order:** within the flow, `signal_instance.raw = redact_raw(...)` is a plain assignment. The masked value is persisted by the first `db_session.commit()` after it, which is the entity commit or the case commit. If the flow returns before any commit, the masked value is committed by the worker's own commit after the call. I did not check whether `raw` is a mutable-tracked JSON column, but reassigning the whole value is detected either way.
- **Response:** the POST response is built from the instance as committed, so it echoes the unmasked `raw` back to the caller.

If you want the payload masked before it is first persisted, the natural place is `create_instance` at `service.py:680`, where `raw` is copied, or in the view before that call. I haven't made that change.

----- next turn -----

Entity extraction now returns every JSONPath match again, and `tests/entity` passes (11 passed).

**Cause:** commit `beb60cc4`, "perf(entity): stop at the first JSONPath match" (Sam Ortega, 2025-09-02). It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`. That kept only the first match per entity type, so the other matching fields never became entities.

**Fix:** I restored `matches = jpath.find(signal_instance.raw)` and removed the comment the commit added. The diff is the exact inverse of that hunk. I didn't change any tests.

I ran only `tests/entity`, not the full suite. Nothing is committed. The earlier incident permission and case filter fixes are still in the working tree too.

----- next turn -----

Masked values can no longer become entities, and `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**Why unrelated instances were grouped:** `signal_instance_create_flow` masks the payload before it extracts entities (`flows.py:60`). Every `session_token` therefore became the literal `"[REDACTED]"`. The JSONPath on that field matched it and created an entity with that value. `get_by_value_or_create` reuses an existing entity for the same value, so all instances shared one entity. The deduplication filter on that entity type then treated them as the same alert and grouped them into one case.

**Fix:** in `src/dispatch/entity/service.py`, the JSONPath extraction now skips any string equal to `MASK`, which it imports from `signal/redaction.py`. The masking itself is unchanged. This is the only place entities are extracted from a payload. There is no regex extraction path. The regex is compiled in `find_entities` but never used to match values.

The check is an exact comparison with `[REDACTED]`. A real payload value that happens to be `"[REDACTED]"` is also skipped, which seems right.

**Test:** `test_find_entities_skips_masked_values` in `tests/entity/test_entity_service.py` is a new test. I didn't change any existing ones. It redacts a payload with `redact_raw`, defines one entity type on the masked `session_token` and one on an unmasked field, and expects only the unmasked value to become an entity. It fails without the fix.

When I temporarily reverted the whole file to the committed version, `test_find_entities_with_field_only` also failed. That is because the committed version still has the `[:1]` bug from `beb60cc4`. My earlier fix for that is also in the working tree.

Nothing is committed.

----- next turn -----

## Recap

**Investigation 1: unguarded mutating routes and the regression**
- Before my changes, five handlers changed data without a `PermissionsDependency`: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident` and `incident.delete_custom_event`.
- Reporting a case or incident is open on purpose, so `create_case` and `create_incident` are by design. I did not examine the other two case routes, `create_case_channel` and `create_case_resources`, any further. They remain unguarded.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_views_permissions.py`, which fails if the check goes missing.

**Investigation 2: restricted cases visible in the cases list**
- `restricted_case_filter` in `src/dispatch/database/service.py` had lost its `and_(...)` grouping. It read as `open OR restricted OR participant`, so every restricted case matched for non-admin users.
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter") introduced it. I restored `open OR (restricted AND participant)`.

**Investigation 3: signal instance flow and masking**
- `POST /signals/instances` stores the instance and commits it unmasked. A worker later runs `signal_instance_create_flow`. That flow masks the payload with `redact_raw`, extracts entities, applies snooze and deduplication filters, and creates a case unless the instance is filtered, is a canary, or the signal has case creation off.
- The default masked keys are `password`, `secret`, `api_key`, `session_token` and `authorization`. They are configurable with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable.
- The unmasked payload is written to the database. The masking happens only after the worker picks the instance up.
- Masking was introduced by commit `d2675cf4` ("feat(signal): mask sensitive raw fields before processing").

**Investigation 4: entity extraction**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath results, so only the first match became an entity. I reverted that line and `tests/entity` passes.

**Investigation 5: unrelated GitHub token alerts grouped into one case**
- Masked `session_token` values all became the entity `"[REDACTED]"`, so the deduplication filter grouped unrelated instances.
- `find_entities` now skips masked values, and `test_find_entities_skips_masked_values` covers it.

Nothing is committed. Six `tests/ai` tests fail with or without my changes, and I did not investigate them.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95