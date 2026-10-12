Six data-changing routes in the two files declare no `PermissionsDependency`. I checked each route decorator by reading the source, without running the app.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
3. `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

Item 5 stands out. Every other incident event route (create, update, export) requires `IncidentEventPermission`. The matching case route, `delete_custom_event` at `case/views.py:574`, requires `CaseEventPermission`. This incident delete route is the only event route in either file with no check, so it is the most likely to be an oversight.

I didn't read the function bodies. Some routes may enforce access inside the handler instead, but they don't declare it on the route.

Three other things I checked:
- `GET /{incident_id}/report/tactical/generate` and `GET /{incident_id}/regenerate` do have permission dependencies. They are GET routes anyway, so they are out of scope.
- Neither file has router-level dependencies or `include_router` calls. A router-wide check would be applied elsewhere, such as where the router is mounted, which I didn't look at.
- That makes five routes, not six.

I made no code changes.

----- next turn -----

Yes, one is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event` in `src/dispatch/incident/views.py`). I restored its check and added a test. Nothing is committed.

**Regression:** commit `28c21e1e`, "refactor(incident): tidy custom event routes", removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from that route. Despite the "refactor" label, it changed who can delete incident timeline events. The other incident event routes kept the check.

**Not regressions:** `create_case_channel` and `create_case_resources` in `src/dispatch/case/views.py`. `create_case_channel` was added without a check in `ced74f33`. For `create_case_resources` I only found the commit that added the `/resources` route (`f08a22b3`), and I didn't open its diff, so I can't say whether it ever had a check. If you don't mean those two to be open, they are still unprotected. That is a separate decision from the regression, so I left them alone.

**Fix:** I put the `IncidentEventPermission` dependency back on the delete route.

**Test:** `tests/incident/test_incident_route_permissions.py` checks that these four incident event routes declare `IncidentEventPermission`:
- create (`POST /{incident_id}/event`)
- update (`PATCH /{incident_id}/event`)
- export (`POST /{incident_id}/exportTimeline`)
- delete (`DELETE /{incident_id}/event/{event_uuid}`)

It reads the route's declared dependencies, so it doesn't need a database or an authenticated request.

**Verification:** with the fix, all 4 tests pass. With the fix stashed, the delete case fails (`assert IncidentEventPermission in []`) and the other 3 pass. I didn't run the rest of the suite.

----- next turn -----

The cause is the case visibility filter in `src/dispatch/database/service.py`, and I've fixed it. The change came in with commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02).

**Cause:** `restricted_case_filter` used to let a non-admin see a case if it was open, or if it was restricted and the user's email matched a participant. That commit flattened the nested `and_(...)` into three separate `or_` branches:

```
Case.visibility == open
Case.visibility == restricted      # now matches any restricted case
IndividualContact.email == me      # now matches any case, whatever its visibility
```

So every non-admin, including the security team member, now sees every restricted case. The matching incident filter (`restricted_incident_filter`) still has the correct form.

**Fix:** I restored the `and_(restricted, participant email == current user)` grouping. The existing tests were not touched.

**Verification:** `tests/database` and `tests/case` pass (40 tests). I didn't run the full suite.

The working tree now holds the uncommitted changes from this and the previous task: `src/dispatch/database/service.py`, `src/dispatch/incident/views.py` and the new `tests/incident/` directory.

----- next turn -----



----- next turn -----

I traced it through the code, and the unmasked payload is written to the database. Masking only happens later, in a separate worker. I changed no code.

**1. The API request** (`signal/views.py:70`, `create_signal_instance`)
- It resolves the project and the signal definition. It looks the definition up by `externalId` or `variant` in the raw payload, then falls back to the project's default signal.
- It returns 404 if none is found.
- It calls `signal_service.create_instance` (`signal/service.py:650`), which copies `raw` as it is received. The only change is a JSON round trip, which turns dates into strings.
- It then calls `db_session.commit()` in the view.
- A duplicate id returns 409.
- The view takes a `BackgroundTasks` argument but never uses it, so the request does not trigger any processing.

**2. The worker** (`signal/flows.py`)
- `main_processing_loop` runs on a loop. `process_organization_signals` picks up to 500 instances where `filter_action IS NULL` and `case_id IS NULL`. These are the unprocessed ones.
- `process_signal_batch` then calls `signal_instance_create_flow` for each instance. `cli.py:1004` also calls it.

**3. The flow** (`signal_instance_create_flow`, `flows.py:46`)
1. **Mask:** `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60).
2. **Entities:** it extracts entities from the now-masked payload and commits.
3. **Filter:** `filter_signal` runs snooze, then dedup. If either applies, the instance is filtered. It may update the Slack signal message if it is attached to a case, and the flow returns.
4. **Canary:** a canary instance is stored and the flow returns.
5. **No case creation:** if `signal.create_case` is false, the flow returns.
6. **Case:** otherwise it works out case type, priority and oncall assignee, creates an open case, links it to the instance and commits.

**Masking**
- **Function:** `redact_raw` in `signal/redaction.py`. It returns a copy and replaces matching values with `"[REDACTED]"`.
- **Matching:** keys match case-insensitively and by exact name, at any depth inside dicts and lists.
- **Default keys:** `password,secret,api_key,session_token,authorization`. That comes from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which can be overridden through that environment variable.
- **Not masked:** keys that merely contain those words, such as `client_secret`, `x-api-key` or `token`. Secrets inside string values are not masked either.

**Is the unmasked payload written to the database?**
- **Yes.** Step 1 commits the raw payload at request time. It stays that way until the worker reaches the instance.
- **Worker down or behind:** the payload stays unmasked, and the worker takes at most 500 instances per organization per pass.
- **Failure in the flow:** `process_signal_batch` rolls back on any exception, so the instance stays unmasked and is retried.
- **No-case outcomes:** filtered, canary and no-case instances are also masked, because masking comes first in the flow.
- **Entities:** they are extracted after masking, so they don't capture the redacted values.
- **Git history:** `d2675cf4` ("mask sensitive raw fields before processing") added the masking.

**Possible fix, if you want one:** call `redact_raw` in `create_instance` before the first commit, and keep the call in the flow as a backstop.

**Separate bug:** in `views.py`, when the request already includes `signal`, `signal_definition`, `external_id` and `variant` are never set. The later `if not signal_definition:` check would then raise a `NameError`. I did not confirm this.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega) caused this. It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`. That kept only the first match for each entity type, so any other matching fields never became entities.

I removed the `[:1]` slice and its comment, which restores the code to how it was before that commit. A JSONPath such as `$..ip` can legitimately match many fields, so the "names one field" assumption in the comment was wrong.

`python -m pytest tests/entity -q` now gives 11 passed. I didn't touch any tests and didn't run the rest of the suite. Nothing is committed, and the working tree still has the earlier uncommitted changes.

----- next turn -----

Masking replaces the session token with the literal `"[REDACTED]"`, and entity extraction was then reading the masked payload. In `signal_instance_create_flow`, `redact_raw` runs before `find_entities`. The JSONPath on `session_token` therefore matched `"[REDACTED]"` on every instance, and every instance got the same entity, `"[REDACTED]"`. Your deduplication filter on that entity type then treated all of those instances as duplicates and put them in one case.

**Fix:** in `src/dispatch/entity/service.py`, `find_entities` now skips any match whose value equals `MASK`, which I import from `dispatch.signal.redaction`. `find_entities` is the only place entities are extracted from a payload, so this covers every caller. The masking itself is unchanged.

Instances with masked values now produce no entity for that type. Deduplication on that entity type will therefore no longer group them.

**Test:** I added `test_find_entities_skips_masked_values` to `tests/entity/test_entity_service.py`. It masks a payload containing `session_token`, then extracts with a JSONPath on that field and expects no entities.
- The new test fails without the fix.
- `python -m pytest tests/entity -q` gives 12 passed with it. I didn't run the rest of the suite.
- The existing tests are untouched. I only appended the new one.

**Not committed:** the earlier changes are still in the working tree: `src/dispatch/database/service.py`, `src/dispatch/incident/views.py`, `tests/incident/`, plus this task's two files.

----- next turn -----

## Recap

**1. Unprotected data-changing routes**
- Before my changes, five handlers in `case/views.py` and `incident/views.py` changed data without a `PermissionsDependency`. I re-checked this against the committed `HEAD` versions of both files.
- Four are open or unconfirmed: `create_case`, `create_case_channel`, `create_case_resources` and `create_incident`. You said anyone may report a case or an incident.
- The fifth was a regression. Incident `delete_custom_event` lost its `IncidentEventPermission` check in commit `28c21e1e`.
- I restored the check and added `tests/incident/test_incident_route_permissions.py`. It covers the four incident event routes, and I saw it fail without the fix.

**2. Restricted cases leaking into the cases list**
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter") flattened the nested `and_` in `restricted_case_filter`.
- Every non-admin then matched every restricted case.
- I restored the `and_` grouping. The existing tests are untouched, and `tests/database` and `tests/case` pass.
- I added no new test for this filter.

**3. Signal instance flow and masking**
- `POST .../signals/instances` stores the instance and its raw payload as received, then commits.
- A separate worker (`main_processing_loop`) later calls `signal_instance_create_flow`.
- The flow masks the payload with `redact_raw`, extracts entities, filters (snooze, then dedup), and either opens a case or stops.
- Masking only matches exact key names, case-insensitively. The unmasked payload is written to the database at request time and stays there until the worker processes the instance.

**4. Entity extraction**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath matches, so only the first match became an entity.
- I removed it, and `tests/entity` passes.

**5. Masked values grouping unrelated cases**
- Entities were extracted from the already-masked payload, so every instance got the entity `"[REDACTED]"`. The dedup filter then grouped unrelated instances into one case.
- `find_entities` now skips masked values, and I added `test_find_entities_skips_masked_values`. It fails without the fix.
- Masking itself is unchanged, and the first signal-masking commit is `d2675cf4`.

I didn't run the full suite, and nothing is committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965
VISIBILITY_BUG: 42699ebc7cdb
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435
MASKING_COMMIT: d2675cf4b078