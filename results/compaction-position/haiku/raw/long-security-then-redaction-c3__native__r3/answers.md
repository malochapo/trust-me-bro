Five write routes have no `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""`: `create_case`, line 162
2. `POST /{case_id}/resources/conversation`: `create_case_channel`, line 236
3. `POST /{case_id}/resources`: `create_case_resources`, line 260

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""`: `create_incident`, line 117
5. `DELETE /{incident_id}/event/{event_uuid}`: `delete_custom_event`, line 503

Every other POST, PUT, PATCH and DELETE route in both files declares a `PermissionsDependency`. The two GET routes that use `IncidentEditPermission` (incident lines 365 and 595) are read-only, so they are out of scope.

Both routers are mounted under `authenticated_organization_api_router` in `src/dispatch/api.py` (lines 176 and 191), and that mount adds no `PermissionsDependency`. I did not check what authentication that parent router applies, so these five routes may still require a login. They have no permission check at the route level, though.

I made no code changes.

----- next turn -----

The regression is `delete_custom_event` (`DELETE /incidents/{incident_id}/event/{event_uuid}`). Commit `28c21e1e` ("refactor(incident): tidy custom event routes") deleted its `IncidentEventPermission` line and changed nothing else. I restored the line, and added a test that fails when it is missing.

The other four routes are not regressions:
- `create_case` and `create_incident` are the open reporting endpoints you described as intentional.
- `create_case_channel` (`ced74f33`) and `create_case_resources` (`f08a22b3`) were added without any permission check. History shows no removal, so this looks like an unprotected addition rather than a regression. I didn't change them. You may want to decide whether they should get a check, probably `CaseEditPermission` or `CaseEventPermission`.

**Changes**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on the `delete_custom_event` route.
- `tests/incident/test_incident_views.py` (new): inspects the registered `DELETE /{incident_id}/event/{event_uuid}` route and asserts that `IncidentEventPermission` is among its `PermissionsDependency` classes. I removed the line temporarily and the test failed. With the fix it passes.

**Tests:** `python -m pytest tests/incident tests/case` gives 16 passed.

----- next turn -----

The cases list was leaking restricted cases to members who are not participants. I've fixed it, and the database and case tests pass (40 passed).

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` lets any restricted case through with no participant check. The `Case.visibility == Visibility.restricted` condition sat on its own in the `or_`, outside the `and_` that requires the user's email to match a participant. The incident filter has the grouping right.

**Commit:** `42699ebc7` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). It was labelled a refactor, but it changed the logic: the `and_(...)` wrapper was removed, which dropped the participant check.

**Fix:** restored the `and_(restricted, participant email matches)` grouping. No tests were changed. `member` users now see only open cases plus restricted cases they take part in. The existing member test expects exactly that (3 of 4 cases).

I did not run the suite against the unfixed code, so I haven't seen the test fail before the fix. The expected member count of 3 was the check I relied on.

----- next turn -----



----- next turn -----

**Short answer:** Sensitive values are masked in `src/dispatch/signal/redaction.py` by `redact_raw`, called from `signal_instance_create_flow` in `src/dispatch/signal/flows.py:60`. By default it masks `password`, `secret`, `api_key`, `session_token` and `authorization`. Yes, the unmasked payload is written to the database. The POST handler commits it before any masking runs.

**The path, step by step**

1. **HTTP handler.** `POST /instances` is `create_signal_instance` in `src/dispatch/signal/views.py` (decorator at line 70). It resolves the project and the signal definition. It then calls `signal_service.create_instance` and runs `db_session.commit()`. No masking happens here.

2. **Persisting the raw payload.** `create_instance` in `src/dispatch/signal/service.py` (around line 661) copies `signal_instance_in.raw`, round-trips it through JSON, and stores it in `SignalInstance.raw` (a JSONB column). Nothing is masked at this point, so the unmasked payload is committed by the handler in step 1. The `update_instance` function in the same file also stores raw unmasked, but the POST route doesn't call it.

3. **Processing is deferred.** The POST route does not schedule any background task; the `background_tasks` parameter is unused. Processing happens in a separate loop. `main_processing_loop` in `signal/flows.py` calls `get_unprocessed_signal_instance_ids` (`signal/service.py`, around line 900). That selects rows where `filter_action` and `case_id` are both null, oldest first, up to 500. Batches go through `process_signal_batch` into `signal_instance_create_flow`.

4. **Masking.** In `signal_instance_create_flow`, line 60 runs `signal_instance.raw = redact_raw(signal_instance.raw)`, with the comment "mask sensitive values before entities are extracted from the payload". The function is in `src/dispatch/signal/redaction.py`:
   - `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` lower-cases and trims the field names, then calls `_redact`.
   - `_redact` replaces the value of any dict key whose lower-cased name is in the set with `"[REDACTED]"`. It recurses into dicts and lists. Other values are returned unchanged.
   - Defaults come from `src/dispatch/config.py:98–102`, set by the `SIGNAL_REDACTED_RAW_FIELDS` env var: `password,secret,api_key,session_token,authorization`.

5. **Entity extraction.** Entities are extracted after masking. JSONPath matching in `src/dispatch/entity/service.py` (around line 290) reads `signal_instance.raw`, so it sees the redacted copy.

6. **Filtering.** `signal_service.filter_signal` (`signal/service.py:866`) runs snooze and dedup checks. If a filter matches, it sets `filter_action` and the flow returns. It then commits, which is when the redacted raw is first written back to the database.

7. **Case creation.** If nothing filtered the instance, the flow returns early for canary signals or when `signal.create_case` is false. Otherwise it builds a `CaseCreate` (visibility `open`) and calls `case_service.create`. It sets `signal_instance.case` and commits, then starts `case_flows.case_new_create_flow`.

**Is the unmasked payload written to the database?**

Yes. `create_signal_instance` commits the raw payload before masking runs. Masking happens later in the processing loop, and the flow's later commit overwrites the stored value with the redacted copy. Until that loop reaches the row, the database holds the unmasked payload. The window can be long if the loop is backlogged.

Other gaps I noticed:
- The default set doesn't cover keys like `token`, `apiKey` or `access_token`. Matching is exact on the lower-cased key name, not a substring or pattern match.
- Only dict and list structures are walked. Secrets inside JSON-encoded strings are not masked.
- Values are masked whatever their type, so a non-string value under a matching key is also replaced.
- I found no test that covers `redact_raw` or the masking step. `tests/signal/` has flow, filter and service tests, but nothing that checks masking.

I did not change any code or run tests; this was read-only tracing. I checked the 'write before redact' ordering by reading the code, not by running the POST endpoint.

----- next turn -----

Entity extraction now keeps every JSONPath match. `tests/entity` was red and is now green, and no test files were changed.

**Cause:** commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02). It changed `jpath.find(signal_instance.raw)` in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`) to `jpath.find(signal_instance.raw)[:1]`. For an entity type whose JSONPath matches several fields, only the first became an entity. The commit's only change was that one line, so the fix is to revert it.

**Fix:** in `src/dispatch/entity/service.py`, I removed the `[:1]` slice and the comment added with it:
```python
matches = jpath.find(signal_instance.raw)
```

**Tests:**
- Before the fix, `python -m pytest tests/entity -q` failed `test_find_entities_with_field_only` with `assert 1 == 2`.
- After the fix, `python -m pytest tests/entity tests/signal -q` gives 43 passed, 1 skipped.

The `perf` label on that commit suggests the author wanted to save work on large payloads. If that still matters, a different approach would need a fresh decision, since this removes the limit entirely.

The changes are uncommitted. I did not commit anything.

----- next turn -----

Analysts' grouping came from the masked placeholder itself. Masking replaces the token with `"[REDACTED]"`, which is a string. Entity extraction then accepted it as a normal value, so every instance with a masked token got the same `[REDACTED]` entity. The deduplication filter keys on entities, so those unrelated instances were grouped into one case.

**Fix:** `_find_entities_by_jsonpath_expression` in `src/dispatch/entity/service.py` now skips any match whose value equals `MASK` (imported from `dispatch.signal.redaction`). Every extraction path goes through this function, so the check covers them all. Masking itself is unchanged.

**Test:** I added `test_find_entities_never_extracts_masked_values` to `tests/entity/test_entity_service.py`. It masks a payload with `redact_raw`, runs `find_entities` on a session-token entity type and a valid ARN type, and asserts that `[REDACTED]` is not an entity. Existing tests are unchanged.

**Results:**
- Without the fix, the new test fails.
- With the fix, `python -m pytest tests/entity tests/signal -q` gives 44 passed, 1 skipped.

**Not checked:** I did not trace which commit introduced the masking, or whether an earlier version of extraction skipped the placeholder. The changes are uncommitted.

----- next turn -----

**Investigation 1: unprotected write routes and the regression**

- Listed the POST, PUT, PATCH and DELETE routes in the case and incident APIs that had no `PermissionsDependency`. Five handlers qualified: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open by design, since anyone may report a case or incident.
- `create_case_channel` and `create_case_resources` were never protected. They were added without a check in `ced74f33` and `f08a22b3`, so they are not regressions. I left them unchanged and flagged them for a decision.
- `delete_custom_event` was a regression. Commit `28c21e1e` removed its `IncidentEventPermission` check. I restored it in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views.py`. That test fails if the check is removed again; I confirmed it fails without the check and passes with it.

**Investigation 2: restricted cases visible to non-participants**

- The cases list leaked restricted cases. `restricted_case_filter` in `src/dispatch/database/service.py` let any restricted case through without a participant check, because the restricted term sat outside the `and_` grouping.
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed that grouping. I restored it. No tests were changed, and `tests/database/test_service.py` plus `tests/case` pass (40 passed).

**Investigation 3: signal masking, entity extraction, and grouping**

- **Tracing masking:** `POST /api/v1/{organization}/signals/instances` stores the raw payload with `create_instance` and commits it before any masking runs. The processing loop then calls `signal_instance_create_flow`, which masks the payload with `redact_raw` (`src/dispatch/signal/redaction.py`) before entity extraction and filtering.
- **Unmasked payload in the database:** yes. The POST commit stores the unmasked payload, and the redacted copy only overwrites it when the processing loop reaches that instance.
- **Extraction bug:** commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath matches in `find_entities`. I removed it, and `tests/entity` passes.
- **Grouping bug:** the masked placeholder `"[REDACTED]"` was a string, so it passed extraction and became an entity. Every instance with a masked token then shared that entity, and deduplication grouped them. I changed `_find_entities_by_jsonpath_expression` to skip matches equal to `MASK`, and added `test_find_entities_never_extracts_masked_values`. The new test fails without the fix. With the fix, `tests/entity` and `tests/signal` give 44 passed, 1 skipped.

**Open items:**
- All changes are uncommitted, including the new tests.
- Whether `create_case_channel` and `create_case_resources` should get a permission check is a decision for you.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4