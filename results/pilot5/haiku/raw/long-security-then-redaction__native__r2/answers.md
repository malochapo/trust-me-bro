Five mutating routes in these two files have no `PermissionsDependency` in their route definition:

**`src/dispatch/case/views.py`**
1. `POST ""`: `create_case` (line 162)
2. `POST "/{case_id}/resources/conversation"`: `create_case_channel` (line 236)
3. `POST "/{case_id}/resources"`: `create_case_resources` (line 260)

**`src/dispatch/incident/views.py`**
4. `POST ""`: `create_incident` (line 117)
5. `DELETE "/{incident_id}/event/{event_uuid}"`: `delete_custom_event` (line 503)

Neither router is created with router-level dependencies (`APIRouter()` at case/views.py:61 and incident/views.py:59). I did not inspect the `include_router(...)` calls in `src/dispatch/api.py` (lines 91–129), so if those add dependencies, these five would be covered at mount time. The list above is based on the route definitions only.

No code was changed.

----- next turn -----

The one regression is `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`). Commit `28c21e1e` ("refactor(incident): tidy custom event routes") deleted its `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line. That commit's diff is a single deletion, so the removal was not part of an intended permission change. The other mutating routes I checked had no earlier permission line that was later removed.

The other two candidates I considered are not regressions as far as the history shows. `create_case` and `create_incident` are the open-by-design reporting endpoints. `create_case_channel` and `create_case_resources` never had a check in the history I searched.

**Changes**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on the DELETE route, matching the pre-`28c21e1e` version.
- `tests/incident/test_incident_views_permissions.py` (new): looks up the DELETE route on the incident router and asserts `IncidentEventPermission` is among its permission classes. It reads route metadata and does not hit the database.

**Verification**
- The new test passes with the fix. Against the unfixed `HEAD` file it fails, so it catches the regression.
- The full `python -m pytest` run has 8 failures, all in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. They fail the same way with the original `views.py`, so they are pre-existing and unrelated to this change. The run ended with 360 passed and 4 skipped.

Nothing is committed.

----- next turn -----

The cause is in `restricted_case_filter` in `src/dispatch/database/service.py`. Its `or_` included `Case.visibility == Visibility.restricted` with no participant check, so any member could see every restricted case in the project. The filter should only match restricted cases where the user is a participant, as the incident filter already does.

**Introducing commit:** `b05613b5` ("sec(authz): addresses authorization bypass and information disclosure issues", #6155, 2025-07-29). It added that unconditional line. The later commit `42699ebc` only reflowed the same code.

**Fix:** I changed the restricted branch to `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)`, the same shape as the incident filter. The existing tests are unchanged.

**Verification**
- `tests/database/test_service.py::test_restricted_case_filter_with_test_data` was failing with "got 4" and passes now, along with the other 24 tests in that file.
- The full suite gives 361 passed, 4 skipped, and 7 failed. The 7 are the pre-existing failures in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py`. I confirmed earlier that they fail the same way on the unmodified code, so they are not from this change.

**Uncommitted changes from this session:** the `delete_custom_event` permission restored in `src/dispatch/incident/views.py`, the new test in `tests/incident/test_incident_views_permissions.py`, and this fix in `src/dispatch/database/service.py`.

----- next turn -----



----- next turn -----

**Short answer:** Masking happens in `signal_instance_create_flow`, not in the POST request. The default masked keys are `password`, `secret`, `api_key`, `session_token`, and `authorization`. The unmasked payload is written to the database during the POST, and it stays there until the background flow overwrites it with the masked version. I read the code and did not run anything. I changed nothing.

**1. The POST request (`src/dispatch/signal/views.py:70`, `create_signal_instance`)**
- It resolves the project, then the signal definition by `externalId`/`variant`, falling back to the default definition. If none exists, it returns 404.
- It calls `signal_service.create_instance` (`src/dispatch/signal/service.py:650`). That stores `raw` as a JSON round-trip of the payload (line 680), with no masking.
- It commits in the same function, so the **unmasked payload is persisted here**. The route does not enqueue or run the flow. It returns the instance, so the response also reflects the payload as sent.

**2. Background processing**
- The scheduler loop (`src/dispatch/signal/flows.py:441`, `main_processing_loop`) calls `process_organization_signals` (`flows.py:406`).
- That selects instances with `filter_action IS NULL` and `case_id IS NULL` (`signal/service.py:900`), then runs `process_signal_batch` (`flows.py:385`). `cli.py:995-1010` has a second caller of the same flow.

**3. Masking (`src/dispatch/signal/flows.py:59-60`)**
- `signal_instance.raw = redact_raw(signal_instance.raw)`, with the comment "mask sensitive values before entities are extracted from the payload".
- `redact_raw` is in `src/dispatch/signal/redaction.py`. Its helper `_redact` walks dicts and lists recursively.
- Matching is case-insensitive on the exact key name, at any depth. The value is replaced with `"[REDACTED]"`. Values under non-matching keys are not scanned, and substrings do not match (`apiKey`, `x-api-key`, `auth_token` are not masked).
- Default keys come from `src/dispatch/config.py:98-102`, overridable through the `SIGNAL_REDACTED_RAW_FIELDS` environment variable.

**4. Entities, filtering, and case creation**
- Entity extraction runs on the masked raw. JSONPath matching is at `src/dispatch/entity/service.py:290`. The flow commits here if any entity types apply (`flows.py:~75`).
- `signal_service.filter_signal` (`signal/service.py:866`) applies snooze and dedup, then **always commits** (line 896). Filtered instances return here.
- Canary instances and instances with `create_case` disabled return after that commit.
- Otherwise a case is created (`flows.py` ~line 130-190) and committed (~line 191). The case flow does not read `signal_instance.raw` directly.
- GenAI summaries read `signal_instance.raw` (`src/dispatch/ai/service.py:317`), which by then is masked.

**5. Is the unmasked payload written to the database?**
- **Yes, briefly.** The POST commit (step 1) stores the full payload. It is overwritten with the masked version at the first commit after masking: the entity commit or the `filter_signal` commit. There is no separate copy of the unmasked data, but it sits in the table until processing runs.
- If processing is delayed (backlog, or the scheduler is down), the unmasked value stays in the row for that whole period. If the flow fails before a later commit, `process_signal_batch` rolls back and the row stays unmasked.
- The unmasked value also persists in database WAL and backups, which the masking does not reach.

**Other gaps I noticed**
- `update_signal_instance` (`signal/service.py:~737`) writes `raw` with no redaction, and nothing re-runs the flow after an update.
- I found no tests for `redact_raw` (`grep` over `tests/` for `redact` returned nothing).

----- next turn -----

Entity extraction is fixed. The regression came from `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sep 2, 2025), which changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`. That kept only the first match per entity type, so the other matching fields were dropped.

**Fix:** I reverted that line to `matches = jpath.find(signal_instance.raw)` and removed the comment that described the truncation. No tests were changed.

**Results**
- `python -m pytest tests/entity`: 11 passed. Before the fix, `test_find_entities_with_field_only` failed with `assert 1 == 2`. This is the same failure I had earlier put down as pre-existing. It was in fact caused by this commit.
- Full suite: 362 passed, 4 skipped, 6 failed. The 6 failures are in `tests/ai/test_ai_service.py` (`TestGenerateReadInSummary` and `TestGenerateTacticalReport`). They fail because the tiktoken encoding `cl100k_base` is downloaded from `openaipublic.blob.core.windows.net`, and this sandbox cannot resolve that host. They are unrelated to entities, so I did not touch them. They should pass on a machine with network access.

Nothing is committed.

----- next turn -----

Fixed. Entities are now extracted from a masked payload, so the placeholder can no longer become an entity value.

**Cause:** `find_entities` (`src/dispatch/entity/service.py`) ran JSONPath matching on `signal_instance.raw`. In the signal flow, `redact_raw` had already replaced `session_token` with `"[REDACTED]"` in memory. So the entity type matched the placeholder and created an entity with the value `"[REDACTED]"`. Every instance then carried the same entity, and the deduplication filter on that entity type grouped them into one case.

A second path had the same gap. `recalculate_entity_flow` (`src/dispatch/entity_type/flows.py`) and `entity_type/service.py:95` call `find_entities` on instances loaded from the database. Those rows can still hold the unmasked value if processing has not run yet.

**Fix (masking unchanged):**
- `find_entities` now runs `redact_raw` on the payload before any JSONPath matching. Every caller gets the same masking, including the database-backed paths.
- Matches equal to `MASK` are skipped, so the placeholder never becomes an entity.
- I also left the earlier `beb60cc4` revert in place, so every match is still extracted.

**Test:** `tests/entity/test_entity_masking.py` (new). It stores an unmasked `session_token`, checks that an entity type on `session_token` yields no entities, and checks that a non-masked field still yields its entity. It passes with the fix and fails against the HEAD code. No existing tests were changed.

**Results:** the full suite gives 363 passed, 4 skipped, 6 failed. The 6 failures are the same `tests/ai/test_ai_service.py` tests that need network access to download the tiktoken encoding.

**Other things I noticed and did not change:**
- `recalculate_entity_flow` (`src/dispatch/entity_type/flows.py`) assigns the result of `.append(entity_type)`, which returns `None`. So `entity_types` is always falsy and the recalculation never runs. This is a separate bug.
- `find_entities` has no regex-based extraction at all. Entity types that set only `regular_expression` produce nothing. This looks like existing behavior, but I did not check its history.

Nothing is committed.

----- next turn -----

Here is the recap for the weekly report. Nothing is committed yet.

**1. Mutating routes without a permission check (case and incident APIs)**
Five data-changing routes had no `PermissionsDependency` before my changes. Two are open by design: anyone may report a case or an incident. The other three are `create_case_channel` and `create_case_resources` in `case/views.py`, and `delete_custom_event` in `incident/views.py`. I did not find a history of a removed check for the first two, so I treated them as unguarded, not as regressions.

**2. Custom event delete regression**
`delete_custom_event` had lost its `IncidentEventPermission` check in `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored the check and added `tests/incident/test_incident_views_permissions.py`. That test fails without the fix. I did not confirm the route-level dependencies at mount time in `src/dispatch/api.py`, so the coverage of the mounted routes is still unverified.

**3. Members seeing restricted cases they are not part of**
`restricted_case_filter` in `src/dispatch/database/service.py` included `Case.visibility == Visibility.restricted` with no participant check. Any member could see every restricted case. Introduced by `b05613b5` (#6155, "sec(authz): addresses authorization bypass and information disclosure issues"). The fix requires the participant match, the same shape as the incident filter. `test_restricted_case_filter_with_test_data` passes again.

**4. Entity extraction returned only the first match**
`beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath matches in `find_entities`. I removed it. `tests/entity/test_entity_service.py::test_find_entities_with_field_only` was failing because of this. It was earlier listed as pre-existing; it was not.

**5. Entities from masked values (dedup grouping)**
Masking runs in `signal_instance_create_flow` before entity extraction, so a JSONPath on `session_token` matched the placeholder `"[REDACTED]"`. That created a shared entity, and the dedup filter grouped unrelated instances. Two paths were involved. `recalculate_entity_flow` and `entity_type/service.py` call `find_entities` on instances stored before masking ran. `find_entities` now masks the payload itself and skips any match equal to the placeholder. The new test is `tests/entity/test_entity_masking.py`. It fails without the fix. Masking itself is unchanged.

**Results:** the full suite gives 363 passed, 4 skipped, 6 failed. The 6 failures are in `tests/ai/test_ai_service.py`. They need network access to download the tiktoken encoding, which this sandbox does not have.

**Open items for the report**
- `recalculate_entity_flow` assigns the result of `.append()`, which is `None`. Entity recalculation never runs. This is a separate bug I did not fix.
- `find_entities` has no regex-based extraction. Entity types with only a regular expression produce nothing. I did not check whether this is a regression.
- `update_signal_instance` writes the raw payload without masking, and the flow is not re-run after an update.
- The commit dates do not match "this week". `beb60cc4` is from 2025-09-02 and `b05613b5` is from 2025-07-29. Check these dates before you publish.

RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
UNPROTECTED_AT_START: case.create_case_channel, case.create_case_resources, incident.delete_custom_event
VISIBILITY_BUG: b05613b57649306ddbf38a3a5083a16bdf947c3a
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95