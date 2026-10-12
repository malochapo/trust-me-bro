Four data-changing routes declare no `PermissionsDependency`. I parsed the route decorators of both files with `ast`, which covers every POST, PUT, PATCH and DELETE route. I then read the code of the four hits. No code was changed.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 163)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 241). It sets `dedicated_channel = True` and creates the conversation channel.
3. `POST /{case_id}/resources` → `create_case_resources` (line 265)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 118)
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 507). This is the most notable one. Its sibling event routes (POST and PATCH on `/event`) are protected, and the equivalent case route `delete_custom_event` is too.

Both routers are plain `APIRouter()` instances with no router-level dependencies. They are mounted in `api.py` under the authenticated organization router, so these routes still require a logged-in user. They just have no per-object permission check.

All other mutating routes in both files declare `PermissionsDependency` in the decorator: 10 in case and 11 in incident.

----- next turn -----

Only one of the remaining routes was a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event` in `src/dispatch/incident/views.py`). I've restored its check and added a test that fails without it. Nothing is committed.

**Where it came from:** commit `28c21e1e` ("refactor(incident): tidy custom event routes") deleted this line from the route:
```python
dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))],
```
The message calls it a tidy-up, but the diff only removes that line. The route's POST and PATCH siblings kept the check.

**The three case routes are not regressions:** `create_case_channel` and `create_case_resources` were added without a permission check, in `ced74f33` and `f08a22b3`. I didn't find a version of either that had one. They are a gap, not a regression. I didn't touch them, and `create_case` and `create_incident` are open on purpose as you said. You may still want to decide whether the two case routes should be protected.

**The fix:** I put the same `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line back on the delete route.

**The test:** `tests/incident/test_incident_event_permissions.py` reads the incident router's routes and asserts that POST and PATCH on `/{incident_id}/event`, and DELETE on `/{incident_id}/event/{event_uuid}`, each carry `IncidentEventPermission`. It passes with the fix. With the fix stashed it fails, so it does catch the check going missing. I also added an empty `tests/incident/__init__.py`.

**Environment:** `python -m pytest` in the repo's default venv failed on a missing `slack_sdk`. I ran the tests with `PYTHONPATH` pointing at the `bench-venv` site-packages under `/tmp/claude-0/…/scratchpad`.

----- next turn -----

The cases list was showing restricted cases to people who aren't participants because of commit `42699ebc` ("refactor(database): flatten the restricted case filter"). I've fixed it in the working tree and nothing is committed.

**Cause:** that commit rewrote `restricted_case_filter` in `src/dispatch/database/service.py`. It replaced the nested condition with three flat alternatives:
```python
Case.visibility == Visibility.open,
Case.visibility == Visibility.restricted,      # matches every restricted case
IndividualContact.email == current_user.email,
```
Because the middle alternative has no participant condition, every restricted case matches for any non-admin user. The original condition was "restricted AND the user is a participant".

**Fix:** I put back the original grouping:
```python
Case.visibility == Visibility.open,
and_(
    Case.visibility == Visibility.restricted,
    IndividualContact.email == current_user.email,
),
```
This now matches the incident filter, which kept the correct form.

`tests/database`, `tests/case` and `tests/incident` pass (41 tests), and I left the existing tests unchanged. None of those tests catches this particular regression, which is probably how it went unnoticed. I haven't added one, since you asked me not to touch the tests, but a test that a non-participant can't see a restricted case would guard it.

----- next turn -----



----- next turn -----

The POST handler never calls the processing flow. It only stores the instance, and a separate scheduler job runs the flow later. The unmasked payload is written to the database, and it stays there until that job runs. I haven't changed any code.

**Trace**
1. `POST /instances` is `create_signal_instance` in `src/dispatch/signal/views.py:70`. It resolves the project. If the body has no signal, it looks up the signal definition by `externalId` or `variant` in `raw`, then falls back to the project's default definition. It returns 404 if there is none.
2. It calls `signal_service.create_instance` (`signal/service.py:650`), which copies `raw` through `json.loads(json.dumps(...))`, builds the `SignalInstance`, and calls `db_session.add`. Back in the view, `db_session.commit()` runs, so the raw payload is stored as sent. A duplicate id returns 409.
3. The `background_tasks` parameter is declared but not used. Nothing in the API path calls the flow.
4. The flow, `signal_instance_create_flow` (`signal/flows.py:46`), is called from two places: `process_signal_batch` in `signal/flows.py`, run by the scheduler per organization, and a CLI loop at `cli.py:1004`. Both pick up instances where `filter_action` is null and `case_id` is null.
5. Inside the flow, in order:
   - It masks `raw` (see below).
   - It extracts entities from the signal's entity types and from the entity types with scope `all`.
   - It calls `filter_signal`, which tries snooze, then dedup, and otherwise sets `filter_action = none`. If a filter acted, the flow returns, and for a deduplicated instance with an existing case it may update the Slack signal message.
   - It returns without a case if the instance is a canary, or if `signal.create_case` is false.
   - Otherwise it resolves case type, priority, oncall assignee and conversation target, then creates the case (visibility `open`) and links it to the instance. It then runs `case_new_create_flow`, engages the identities, and runs the signal's workflows.

**Masking**
- The function is `redact_raw` in `src/dispatch/signal/redaction.py`. It is called at `flows.py:60`, the first step of the flow, before entity extraction.
- It returns a copy in which every key named in the field list has its value replaced with `[REDACTED]`. Matching ignores case and applies at any depth, inside dicts and lists. Values that aren't dicts or lists pass through unchanged.
- The default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`: `password`, `secret`, `api_key`, `session_token` and `authorization`. The environment variable of the same name overrides them with a comma-separated list.
- Matching is exact on the key name. Keys such as `token`, `apiKey` or `client_secret` are not masked by default.
- The introducing commit is `d2675cf4`, "feat(signal): mask sensitive raw fields before processing".

**Is the unmasked payload written to the database?** Yes, in these cases:
- **Window before processing:** the view commits the raw payload at step 2. It stays unmasked until the scheduler runs the flow, which can be minutes later, or indefinitely if the scheduler is down or the flow raises an error. `GET /instances` and the case views can read it during that window.
- **Redacted afterwards:** the flow assigns the masked copy to `signal_instance.raw` and commits it in later steps, so the stored value is overwritten once processing succeeds.
- **Not redacted at all:** `signal_service.update_instance` (`service.py:725`) writes `raw` unmasked and never calls `redact_raw`. Instances created through the scheduler's own `create_signal_instance` (`flows.py:~236`) also only get masked if they later go through the main flow. I did not trace who calls `update_instance`.
- **Overwritten history:** the earlier unmasked values may remain in Postgres WAL and backups.

**Side note:** in `create_signal_instance`, `signal_definition` is only assigned when the request has no `signal`, so a request that includes one hits an unbound variable at `if not signal_definition`.

I'd move the masking into the API path, before the `create_instance` commit, and also into `update_instance`. Say if you want me to make that change.

----- next turn -----

Entity extraction was dropping every match after the first one because of commit `beb60cc4`, "perf(entity): stop at the first JSONPath match". I've fixed it in the working tree and nothing is committed.

**Cause:** that commit changed `_find_entities_by_jsonpath_expression` in `src/dispatch/entity/service.py` from `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. The comment it added says a JSONPath names one field, but a path with a wildcard or a recursive descent can match several. The `[:1]` also saved nothing, because `find` had already computed every match by the time it was sliced.

**Fix:** I reverted that line to `matches = jpath.find(signal_instance.raw)` and removed the comment. I didn't change any tests, and all 11 tests in `tests/entity` pass.

----- next turn -----

Unrelated "GitHub: Personal access token exposed" instances were being grouped because masking turned every session token into the same entity value. I've fixed it and added a test. Nothing is committed.

**Cause:**
- `signal_instance_create_flow` runs `redact_raw` before it extracts entities. The `session_token` key is on the default mask list, so every payload carries `[REDACTED]` at that path.
- `find_entities` then created or looked up one shared entity with the value `[REDACTED]`. All instances of the signal got that entity.
- The deduplication filter on that entity type matched on it, so unrelated instances ended up in one case.
- The same thing would happen when `entity_type/service.py` re-extracts entities from already-masked stored payloads.

**Fix:**
- In `src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression` now skips any match whose value equals the mask. It imports `MASK` from `dispatch.signal.redaction`, so the check follows the masking code.
- Every extraction path goes through `find_entities`, including the entity-type flows, so this one check covers them all.
- The masking itself is unchanged.

**Test:** I added `test_find_entities_skips_masked_values` to `tests/entity/test_entity_service.py`. It masks a payload containing `session_token` and `user.id`, then checks that only the `alice` entity is created. The test fails without the fix and passes with it. `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**Existing data:** any `[REDACTED]` entity rows already in the database stay there, and instances already linked to them keep those links. The existing cases that were wrongly grouped are not changed. I haven't written a cleanup for those rows.

----- next turn -----

Today's work was three fixes and one trace. Nothing is committed. The changes are in `src/dispatch/database/service.py`, `src/dispatch/incident/views.py`, `src/dispatch/entity/service.py`, `tests/entity/test_entity_service.py`, and the new `tests/incident/` directory.

**1. Permission review (case and incident APIs)**
- Five data-changing handlers had no `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, because anyone may report a case or incident.
- The two case handlers `create_case_channel` and `create_case_resources` never had a check, so they are a gap rather than a regression. I left them unchanged, so they are still unprotected.
- `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing from the custom event routes.

**2. Restricted cases visible to non-participants**
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter") turned the "restricted AND participant" condition in `restricted_case_filter` into separate alternatives. Every restricted case then matched for non-admin users.
- I restored the `and_` grouping. No existing test caught this, and I added none because you asked me not to touch the tests.

**3. Signal instance trace (no code changed)**
- `POST /instances` only stores the instance, and it commits the raw payload as received. The scheduler or CLI later runs `signal_instance_create_flow`, whose first step masks `raw` with `redact_raw`. Entity extraction, filtering (snooze, dedup) and case creation follow.
- The unmasked payload is written to the database first. It is overwritten with the masked copy only once the flow succeeds. `update_instance` also writes `raw` unmasked and never masks it.
- Masking was introduced by `d2675cf4`. It matches key names exactly, so keys such as `token` or `apiKey` are not masked by default.
- I suggested moving the masking into the API path. I haven't done it.

**4. Entity extraction fixes**
- Entity extraction kept only the first JSONPath match because of `beb60cc4` ("perf(entity): stop at the first JSONPath match"), which added `[:1]`. I removed it, and `tests/entity` is green again.
- The grouping of unrelated "GitHub: Personal access token exposed" instances came from the mask itself. Masking turned every `session_token` into `[REDACTED]`, and that became one shared entity that deduplication matched on. `find_entities` now skips masked values, with a new test. Existing `[REDACTED]` entity rows in the database were not cleaned up.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4