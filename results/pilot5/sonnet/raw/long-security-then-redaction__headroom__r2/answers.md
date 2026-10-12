Four state-changing routes declare no `PermissionsDependency`. I checked every POST, PUT, PATCH and DELETE route in both files. I haven't changed any code.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162). It has no `dependencies=` argument.
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236). It has no `dependencies=` argument.
3. `POST /{case_id}/resources` → `create_case_resources` (line 260). It has no `dependencies=` argument.

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117). It has no `dependencies=` argument.
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503). It has no `dependencies=` argument. This stands out because the matching case route, `delete_custom_event`, requires `CaseEventPermission`, and the other incident event routes require `IncidentEventPermission`.

That is five routes in total (three case, two incident), not four.

Some other things you may want to know:
- **No other route registration:** Neither file registers routes any other way, such as `add_api_route`.
- **Router-level dependencies:** I only read the route definitions in these two files. The routers may get dependencies where they are included, for example in `api.py`. If so, authentication or permission checks may still apply to the routes above. I didn't check that.
- **Possible overlap with `create_incident_resources`:** The `POST /{incident_id}/resources` route, `create_incident_resources`, requires only `IncidentViewPermission`. It does declare a permission, so it isn't on the list, but a view-level permission on a write operation looks weak.
- **GET routes that write:** The incident `GET /{incident_id}/regenerate` route (`generate_summary`) and the `GET .../report/tactical/generate` route (`generate_tactical_report`) may modify data. They are outside the scope you set, and both do declare permissions.

----- next turn -----

Yes, one of the routes is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event` in `src/dispatch/incident/views.py`). I've restored its permission check and added a test for it.

**Which route was the regression**
- Commit `28c21e1e`, "refactor(incident): tidy custom event routes" (Sam Ortega, 2025-07-14), removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from this route. The commit message describes a tidy-up, so the removal looks accidental.
- The other custom-event routes (create, update, export) still have the check, and so does the matching case delete route. Without it, any authenticated user could delete incident timeline events.

**The other two routes without a check are not regressions**
- `create_case_channel` (`POST /{case_id}/resources/conversation`) was added in commit `ced74f33` with no `dependencies=` argument.
- `create_case_resources` (`POST /{case_id}/resources`) has also never had a `PermissionsDependency`, going by the git history for `src/dispatch/case/views.py`.
- Neither route ever had a check that was later removed, so they look like a gap from when they were written. You may still want a permission on them.

**Changes (not committed)**
- `src/dispatch/incident/views.py`: put back the exact `dependencies=` line that commit `28c21e1e` removed.
- New `tests/incident/test_incident_event_views.py`: finds the DELETE route on the incident router and asserts that `IncidentEventPermission` is among its `PermissionsDependency` classes.

**Test results**
- With the fix, the test passes.
- With the `src` change stashed (check missing), the test fails.
- I ran only this new test file, not the full suite.

----- next turn -----

The cause is commit `42699ebc`, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2025-09-02). I've fixed it in `src/dispatch/database/service.py`, but I haven't committed anything.

**The bug:** `restricted_case_filter` decides which cases a non-admin user can see. The commit removed the `and_(...)` wrapper, which turned the visibility clause into three separate OR conditions:
- `visibility == open`
- `visibility == restricted` on its own
- `participant email == current user`

Because `visibility == restricted` now matched by itself, every restricted case passed the filter for members and users with no role. Admin, owner and manager roles skip this filter, so only those other roles were affected.

**The fix:** I put the `and_` back. A restricted case is now visible only when the user is a participant, and open cases stay visible to everyone. The sibling `restricted_incident_filter` was never changed and still has the correct form.

**Tests:**
- `tests/database`, `tests/case` and `tests/incident` all pass (41 tests). I didn't change any existing tests.
- I didn't add a regression test for this one, since you only asked for the fix. Say so if you want one.
- Six tests in `tests/ai` fail, but they fail without my change too (checked with my changes stashed). They look unrelated, and I didn't investigate them.

----- next turn -----



----- next turn -----

I've traced the whole path and have what I need. This is the answer, and I haven't changed any code.

## Path of `POST /api/v1/{organization}/signals/instances`

1. **Handler:** `create_signal_instance` in `signal/views.py:70`, rate-limited to 1000/minute.
   - It resolves the project and the signal definition, looking them up by `raw["externalId"]` or `raw["variant"]` and falling back to the project's default definition. It returns 404 if there is none.
   - It calls `signal_service.create_instance(...)` (`signal/service.py:650`) and then `db_session.commit()`.
   - A duplicate id gives 409.
   - The handler takes `background_tasks` but never uses it, so it does not run the flow.
2. **Processing is deferred.** The instance is stored with `filter_action` and `case_id` both NULL. A separate scheduled job picks up those unprocessed instances: `process_signal_batch` in `signal/flows.py:~386`, and a similar loop at `cli.py:~1004`. Both call `signal_instance_create_flow` (`flows.py:46`) and commit after each instance.
3. **`signal_instance_create_flow`:**
   - It redacts the payload (see below).
   - It extracts entities from the redacted payload and commits.
   - It calls `signal_service.filter_signal`. If a filter matches (dedupe, snooze and so on), it logs the result and returns. For a deduplicated signal with an existing case, it updates the Slack signal message.
   - If the instance is a canary, or the signal has `create_case` off, it returns without a case.
   - Otherwise it resolves the case type, priority, severity, oncall and conversation target. It creates the case with `case_service.create` (visibility `open`), attaches it to the instance, commits, and runs `case_new_create_flow`.

## Masking

- **Where:** `signal/redaction.py`, called from `signal/flows.py:60`: `signal_instance.raw = redact_raw(signal_instance.raw)`.
- **Function:** `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)`, which recurses through the private `_redact`.
  - It returns a copy with the value of any matching key replaced by `"[REDACTED]"`.
  - Keys match case-insensitively, at any depth, inside dicts and lists.
  - It masks the whole value, so a matching key holding a dict is replaced entirely.
  - It only matches on key names, never on value contents.
- **Default keys** (`config.py:98`): `password`, `secret`, `api_key`, `session_token`, `authorization`. The `SIGNAL_REDACTED_RAW_FIELDS` environment variable overrides them. The match is on the exact key name, so `client_secret` or `x-api-key` would not be masked.

## Is the unmasked payload written to the database?

Yes. `create_instance` stores `raw` as received, and the view commits it at `views.py:~117`. That happens before the redaction step, which only runs later in the deferred job.

- **Window:** the unmasked payload sits in the database until the job processes that instance, and the redacted copy then overwrites it. If the job never reaches it, or the flow fails and rolls back, it stays unmasked.
- **Other path:** `signal_service.update_instance` (`service.py:~730`) overwrites `raw` with the unmasked payload and does not redact.
- **Fixed in the original request?** No. If the intent is "never store secrets", redaction needs to happen in `create_instance` and `update_instance` before the first write.

## Other bugs I noticed in the handler

- In `create_signal_instance`, if the request already carries a `signal`, `signal_definition`, `external_id` and `variant` are never assigned. The next `if not signal_definition` check then raises `UnboundLocalError`.
- `flows.py:55` has `"%%s"` in a log call, which prints a literal `%s`.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02) caused it. I've reverted its one-line change in `src/dispatch/entity/service.py`, and `tests/entity` now passes (11 tests). I haven't committed anything.

In `find_entities`, that commit changed `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. The slice kept only the first match per entity type. A JSONPath like `$..ip` can match several fields, and each match should become its own entity. The comment it added ("a JSONPath names one field") was wrong.

I did not change any tests.

----- next turn -----

Unrelated instances were being grouped because a masked value became an entity. The masking replaces the session token with the same string, `[REDACTED]`, in every payload. The entity extraction then created one shared entity from that string for all instances. The deduplication filter on that entity type then saw every instance as a duplicate of the others.

**Fix:** `find_entities` in `src/dispatch/entity/service.py` is the one function every caller of entity extraction goes through. That includes `signal_instance_create_flow`, `entity_type/flows.py` and the `entity_type/service.py` re-scan. It now does two things:
- It runs the payload through `redact_raw` before matching JSONPaths. A payload that hasn't been masked yet (it is stored unmasked until the deferred job runs) can no longer give up a real secret as an entity.
- It skips any match whose value is `[REDACTED]`.

The masking itself is unchanged.

**Test:** I added `test_find_entities_ignores_masked_values` to `tests/entity/test_entity_service.py`. It checks an unmasked payload and an already-masked one, with an entity type on `$..session_token` and another on `user`. Only the `user` entity should come out each time. It fails without the fix, and I didn't change any existing test.

`tests/entity` and `tests/signal` pass (44 passed, 1 skipped). Nothing is committed.

**Existing entities:** entities already created with the value `[REDACTED]` stay in the database. The fix doesn't remove them, and they may still link old instances to cases.

----- next turn -----

## Recap

**1. Permission review (case and incident APIs)**
- Before my changes, five data-changing routes had no `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, because anyone may report a case or incident. I left `create_case_channel` and `create_case_resources` untouched and only reported them.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` removed its `IncidentEventPermission` dependency. I restored it and added `tests/incident/test_incident_event_views.py`, which fails if the check goes missing again.

**2. Restricted cases visible to non-participants**
- Commit `42699ebc` flattened `restricted_case_filter` in `src/dispatch/database/service.py`. It removed the `and_` wrapper, so any restricted case matched the filter for members.
- I restored the `and_`, so a restricted case now shows only to its participants. I did not add a test for this fix.

**3. Signal instance flow and masking**
- `POST /signals/instances` stores the instance and commits it. A scheduled job later runs `signal_instance_create_flow`, which masks the payload, extracts entities, applies filters and either creates a case or stops.
- `redact_raw` in `dispatch.signal.redaction` does the masking. Its default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- The unmasked payload is written to the database first. The masked copy replaces it only when the job later processes that instance. `update_instance` also stores `raw` unmasked.
- The masking was introduced by commit `d2675cf4`.

**4. Entity extraction**
- Commit `beb60cc4` added `[:1]` to the JSONPath matches, so only the first match became an entity. I reverted it, and `tests/entity` passes.
- Grouping of unrelated GitHub-token instances came from the masked value `[REDACTED]` becoming an entity. `find_entities` now extracts from a redacted copy and skips `[REDACTED]` values. I added `test_find_entities_ignores_masked_values`.

**Test state:** `tests/database`, `tests/case`, `tests/incident`, `tests/entity` and `tests/signal` pass. Six `tests/ai` tests fail with or without my changes, and I did not investigate them. Nothing is committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4