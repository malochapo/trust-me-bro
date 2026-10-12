Five data-changing routes declare no `PermissionsDependency` in their route definition. I checked every POST, PUT, PATCH and DELETE route in both files. I did not change any code.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` – `create_case` (line 162)
2. `POST "/{case_id}/resources/conversation"` – `create_case_channel` (line 236)
3. `POST "/{case_id}/resources"` – `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` – `create_incident` (line 117)
5. `DELETE "/{incident_id}/event/{event_uuid}"` – `delete_custom_event` (line 503)

Every other write route in both files has a `dependencies=[Depends(PermissionsDependency([...]))]` entry.

- **Delete-event inconsistency:** the incident `delete_custom_event` is the notable gap. The matching case route (`case/views.py:574`) requires `CaseEventPermission`, and the incident create, update and export event routes all require `IncidentEventPermission`.
- **Router-level dependencies:** both files create a bare `APIRouter()`, so nothing in these files applies a permission to the routes above. Dependencies could still be added where the router is mounted (for example in `api.py`). I did not check that.

----- next turn -----

Yes, one of them is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event` in `incident/views.py`). I've restored its check and added a test, but I haven't committed anything.

**The regression**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, 2025-07-14) removed the line `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]`. The commit touches only that one line, and its message calls it a refactor.
- The route has had a permission check since it was added in `319b2faf`. That commit used `IncidentCommanderOrScribePermission`, and `328359b5` later changed it to `IncidentEventPermission`.
- The sibling routes for creating, updating and exporting incident events, and the case equivalent, all still require their event permissions.

**The other two case routes are not regressions**
`create_case_channel` and `create_case_resources` have never had a `PermissionsDependency`. I checked their history back to `f08a22b3` (their introduction) and `ced74f33`. They look like long-standing gaps or design choices rather than something that was removed. They are still worth a separate look, since both change a case's resources.

**The fix**
I put the `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line back on the route in `src/dispatch/incident/views.py`.

**The test**
`tests/incident/test_incident_view_permissions.py` (plus an `__init__.py`) looks up the DELETE route and asserts that `IncidentEventPermission` is among its declared `PermissionsDependency` classes. It reads the route definition, so it needs no database or auth setup. With the fix stashed it fails, and with the fix in place it passes. I only ran `tests/incident`, not the full suite.

----- next turn -----

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` let a restricted case through for any user. Its condition had become `open OR restricted OR participant-email-matches`, so every restricted case passed the first two terms whatever the participant check said. Admin, owner and manager roles skip this filter, but everyone else, including the security-team member, hit the bug.

**Commit that introduced it:** `42699ebc`, "refactor(database): flatten the restricted case filter". It replaced `and_(Case.visibility == restricted, IndividualContact.email == current_user.email)` with two separate `or_` terms, which changed the logic. The preceding commit `b05613b5` (the authz hardening) had the correct `and_` form. `restricted_incident_filter` still has it, so incidents weren't affected.

**Fix:** I put the `and_(...)` back in `restricted_case_filter`. A user now sees open cases, plus restricted cases only where they are a participant. I didn't touch any existing tests. `tests/database`, `tests/case` and `tests/incident` all pass (41 tests).

I haven't committed anything. The working tree now holds this fix together with the earlier incident permission fix and its new test.

----- next turn -----



----- next turn -----

Short answer: the unmasked payload is written to the database first, and masking only happens later when a worker processes the instance. This is from reading the code. I haven't run it or changed anything.

**Trace**

1. **`POST /instances`** is `create_signal_instance` in `signal/views.py:70`. It resolves the project, then picks a signal definition by `externalId` or `variant`. If none matches it uses the project's default definition, and returns 404 if there is no default.
2. **`signal_service.create_instance`** (`signal/service.py:650`) builds the `SignalInstance` with `raw=json.loads(json.dumps(signal_instance_in_raw))`. This is a plain copy of the request payload with no masking. It also takes `raw["id"]` as the primary key, and an id that isn't a valid UUID returns 400.
3. **Commit.** The view calls `db_session.commit()` and returns. A duplicate id returns 409. The view doesn't call the processing flow, even though it takes a `BackgroundTasks` argument.
4. **Pickup.** Processing runs asynchronously in a separate worker. It picks up instances with `filter_action IS NULL` and `case_id IS NULL`, either through `process_organization_signals` and `process_signal_batch` (`signal/flows.py` ~385–420) or the loop in `cli.py` ~1004. Both call `signal_instance_create_flow` and commit after each instance.
5. **`signal_instance_create_flow`** (`signal/flows.py:46`) then runs these steps:
   - It masks `raw` (line 60).
   - It extracts entities from the masked payload.
   - It commits.
   - It calls `signal_service.filter_signal`. A snooze or dedup action stores the instance and stops. If a case already exists, it may update the Slack signal message.
   - Canary instances are stored and the flow stops.
   - If the signal's `create_case` is false, the instance is stored and the flow stops.
   - Otherwise it works out case type, priority, oncall assignee and conversation target, creates the case with `visibility=open`, and runs `case_new_create_flow`.
   - It runs engagements and workflows last.

**Masking**

- **Function:** `redact_raw` in `src/dispatch/signal/redaction.py`, with the recursive helper `_redact`. It is called only from `signal_instance_create_flow`, at `flows.py:60`.
- **Behaviour:**
  - It returns a copy.
  - Keys are matched case-insensitively, at any depth, inside dicts and lists.
  - A matching key's value becomes `"[REDACTED]"`, even if that value is a nested object.
  - Only keys are checked, never values, so a secret inside a free-text string is not caught.
- **Default keys:** `password`, `secret`, `api_key`, `session_token`, `authorization`. They come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which is overridable through an env var as a comma-separated list.
- **Matching is exact on the whole key.** `api-key`, `apiKey`, `token`, `access_token` and `client_secret` are not masked by default.

**Is the unmasked payload written to the database?** Yes.

- The API request commits it at step 3, so it sits in the `raw` column until a worker reaches that instance.
- The flow then reassigns `raw` to the masked copy. That overwrites the stored value when the next commit runs, which is the entity commit if the signal has entity types, otherwise a later one.
- **Failure window:** if the flow raises before that commit, the batch loops roll back and leave the stored payload unmasked. The next pass would retry it.
- **Redundant copies:** masking only rewrites the `raw` column. The sensitive values stay in the database's write-ahead log and backups. Anything that reads the instance before the worker runs, such as `GET /instances`, sees the unmasked payload.

**Related issues I noticed**

- In `create_signal_instance` in `signal/views.py`, `signal_definition` and `external_id` are only assigned when `signal_instance_in.signal` is empty. If a client passes `signal`, the `if not signal_definition` check raises `NameError`.
- `log.error("... %%s", ...)` in `signal_instance_create_flow` has a doubled `%` in the format string, so the id won't be interpolated.

If you want the secrets never to reach the database, the fix would be to call `redact_raw` in `create_instance` before the `SignalInstance` is built. Entity extraction would then run on masked data. If any entity type or filter depends on a masked field, that is a behaviour change to check first.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") caused it. In `find_entities` in `src/dispatch/entity/service.py`, it changed `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. Only the first match per entity type became an entity.

I reverted that line and its comment, so every match is used again. `python -m pytest tests/entity` now gives 11 passed, and I didn't change any tests. The commit's performance goal isn't met anymore, but it can't be done by dropping matches. I haven't committed anything.

The working tree still has the earlier uncommitted changes (the case visibility filter and the incident permission fix with its test), alongside this one.

----- next turn -----

The cause was the masking step. The `GitHub: Personal access token exposed` signal's entity type points at the session token, so the entity values for all its instances became the literal `[REDACTED]`. `signal_instance_create_flow` masks `raw` and then extracts entities, so every instance got an entity with the same value. The deduplication filter on that entity type saw them as identical and grouped unrelated instances into one case.

**Fix** (`src/dispatch/entity/service.py`, in `find_entities`): the masking itself is unchanged.
- `find_entities` now masks the payload itself before running the JSONPath, using the existing `redact_raw`. An instance that hasn't been processed yet still holds its raw secret, so without this the real token could become an entity.
- It skips any match whose value is `[REDACTED]`. This also covers a JSONPath that points at a whole masked subtree.

`find_entities` is the only place entities are extracted. The API flow, `entity_type/service.py` (when an entity type is created or updated) and `entity_type/flows.py` all call it, so all three are covered.

**Effect on the signal:** the token entity is simply absent now, so the deduplication filter on that entity type no longer matches. If analysts want that signal deduplicated, the filter needs a non-secret entity type.

**Test:** I added `test_find_entities_never_yields_masked_values` to `tests/entity/test_entity_service.py`. It checks a top-level key, a mixed-case nested key and a masked subtree, with both an unmasked and an already-masked payload. Only the non-sensitive entity comes out. I confirmed it fails without the fix and passes with it. `tests/entity`, `tests/signal` and `tests/entity_type` give 50 passed and 1 skipped, and I changed no existing tests.

Existing entities already stored with the value `[REDACTED]` and the cases grouped under them are not cleaned up. I haven't committed anything. The working tree still holds the earlier changes too.

----- next turn -----

Here is the recap of both investigations. Nothing is committed, and the working tree holds all the fixes.

**1. Permission review and regression (case and incident APIs)**
- I checked every POST, PUT, PATCH and DELETE route for a missing `PermissionsDependency`. Before my changes there were five: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident` and `incident.delete_custom_event`.
- Anyone may report a case or incident, so `create_case` and `create_incident` are intentional. The only regression was `incident.delete_custom_event`.
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") dropped its `IncidentEventPermission` check.
- I restored the check in `src/dispatch/incident/views.py`. I added `tests/incident/test_incident_view_permissions.py`, which fails if the check goes missing again.
- I did not look into whether `case.create_case_channel` and `case.create_case_resources` are missing a check on purpose.

**2. Restricted cases shown to non-participants**
- `restricted_case_filter` in `src/dispatch/database/service.py` had lost its `and_(restricted, participant email matches)` grouping. Every restricted case therefore matched for non-admin roles.
- Commit `42699ebc` ("flatten the restricted case filter") introduced it, and I restored the grouping. The existing tests are unchanged and passed.
- I added no dedicated test for this one.

**3. Signal instance flow and masking**
- `POST /signals/instances` stores the instance with the raw payload as sent. A worker later runs `signal_instance_create_flow`, which masks the payload, extracts entities, filters or deduplicates, and may open a case.
- `redact_raw` in `dispatch.signal.redaction` does the masking. It matches keys case-insensitively at any depth and replaces their values with `[REDACTED]`. It was introduced in `d2675cf4` ("mask sensitive raw fields before processing").
- The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- The unmasked payload is written to the database, because the API commits it before the worker masks it.

**4. Entity extraction misses values**
- Commit `beb60cc4` ("stop at the first JSONPath match") added `[:1]` to the JSONPath results in `find_entities`. I reverted it, and `tests/entity` passes.

**5. GitHub token signal grouped into one case**
- Masking ran before entity extraction, so the token entity was always `[REDACTED]`. The deduplication filter saw identical values and grouped unrelated instances.
- `find_entities` now masks the payload itself and skips masked values. This covers all three callers. I added `test_find_entities_never_yields_masked_values`, which fails without the fix.
- Entities already stored as `[REDACTED]`, and the cases grouped under them, are not cleaned up.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95