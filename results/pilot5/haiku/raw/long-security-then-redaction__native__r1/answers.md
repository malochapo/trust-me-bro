Five write routes have no `PermissionsDependency` in their route definition:

**`src/dispatch/case/views.py`**
- `create_case`: `POST ""` (line 162, "Creates a new case.")
- `create_case_channel`: `POST /{case_id}/resources/conversation` (line 236)
- `create_case_resources`: `POST /{case_id}/resources` (line 260)

**`src/dispatch/incident/views.py`**
- `create_incident`: `POST ""` (line 117, "Creates a new incident.")
- `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}` (line 503, "Deletes a custom event.")

I checked every `@router.post/put/patch/delete` decorator in both files. All other write routes declare a `PermissionsDependency`. I only looked at the route decorators, as you asked. If the routers are mounted with a dependency in the API router include (e.g. `include_router(..., dependencies=...)`), these routes could still be protected at runtime. I did not check that, and no code was changed.

----- next turn -----

Only one of the five is a regression: `delete_custom_event` (`DELETE /{incident_id}/event/{event_uuid}` in `src/dispatch/incident/views.py`). The other four were never protected, so they are not regressions:

- `create_case` and `create_incident` are the open-on-purpose reporting endpoints.
- `create_case_channel` and `create_case_resources` were added in `ced74f33` and `f08a22b3` with no check. I treated them as unprotected by design, not as regressions, but they may still need a look.

**Cause:** commit `28c21e1e` ("refactor(incident): tidy custom event routes") deleted the `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line from that route. The commit message describes a refactor, and it removed a permission check. Its sibling event routes still have `IncidentEventPermission`.

**Changes:**
- `src/dispatch/incident/views.py`: restored the `IncidentEventPermission` dependency on `delete_custom_event`.
- `tests/incident/test_incident_views_permissions.py` (new): a test that looks up the route and asserts that `IncidentEventPermission` is among its declared permission classes. It checks the route definition rather than making a request, so it does not depend on a database fixture or a user setup.

**Verification:**
- The new test passes with the fix.
- With the fix temporarily reverted, the test fails, so it catches the regression.
- `python -m pytest tests/case tests/incident` gives 16 passed.

I did not run the full test suite. I also did not check whether the routers are mounted with an extra dependency in `src/dispatch/api.py`. That would not change the finding, since the route-level check is what was removed.

----- next turn -----

The cause is in `restricted_case_filter` in `src/dispatch/database/service.py`. The commit that introduced it is `42699ebc` ("refactor(database): flatten the restricted case filter"), by Sam Ortega, dated 2 Sep 2025.

**What went wrong:** the filter's `or_` had three conditions: `Case.visibility == open`, `Case.visibility == restricted`, and `IndividualContact.email == current_user.email`. The refactor split the restricted and participant checks into separate branches, so any user with a non-admin role could see every restricted case, whether or not they were a participant. The commit was meant to flatten the code, but it removed the `and_` that required both conditions together. The incident version of the filter still has the `and_`, which is why only cases were affected.

**Fix:** I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` branch, matching the incident filter. I did not change any tests.

**Verification:**
- `python -m pytest tests/database/test_service.py tests/case` passes (40 tests).
- Run against the buggy version, `test_restricted_case_filter_with_test_data` fails with 4 cases returned where it expects fewer, so the existing test already covers this bug.

I did not run the full suite. I also did not check whether the list endpoint is reached only through this filter. `get_cases` calls `search_filter_sort_paginate`, which applies `apply_model_specific_filters`, and that is where this filter is applied.

Uncommitted changes in the working tree from earlier turns: the `delete_custom_event` permission restore in `src/dispatch/incident/views.py`, the new `tests/incident/` test, and this fix in `src/dispatch/database/service.py`.

----- next turn -----



----- next turn -----

The route only stores the payload. Masking happens later, in a separate scheduler pass, and the unmasked payload is written to the database before that pass runs.

**Path, step by step**

1. **Route:** `create_signal_instance` at `src/dispatch/signal/views.py:70-73` handles `POST /instances`. It resolves the project and the signal definition (by external id or variant, falling back to the default). It then calls `signal_service.create_instance` and `db_session.commit()` (`views.py:121-127`). The route never calls the flow, so nothing is masked here.

2. **Storage:** `create_instance` (`src/dispatch/signal/service.py:650-700`) copies `raw` and stores it in `SignalInstance.raw` (JSONB, `signal/models.py:239`). The copy is not redacted. The commit in step 1 writes the raw payload to the database, unmasked.

3. **Background processing:** `main_processing_loop` (`src/dispatch/signal/flows.py:441`) polls `get_unprocessed_signal_instance_ids` (`signal/service.py:900`). That query selects instances with `filter_action IS NULL` and `case_id IS NULL`, up to 500 at a time. Each batch goes through `process_signal_batch` (`flows.py:385`), which calls `signal_instance_create_flow` and commits after each instance.

4. **Masking:** `signal_instance_create_flow` (`flows.py:46`) runs `signal_instance.raw = redact_raw(signal_instance.raw)` at `flows.py:60`, before entity extraction. The comment there says so explicitly.

5. **Entities, then filter:** `entity_service.find_entities` runs on the masked payload. Then `signal_service.filter_signal` (`signal/service.py:866`) applies snooze and deduplication. It sets `filter_action` (`none` if nothing matched) and commits (`service.py:896`). If the instance is filtered, the flow returns at `flows.py:78-97`.

6. **Case creation:** If not filtered, the flow returns early for canary signals or for signals with `create_case` off. Otherwise it resolves case type, priority and oncall service, then creates the case (`flows.py:~120-180`). The case is created with `Visibility.open` at `flows.py:179`. I did not trace that function's internals.

**The masking function**

- `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` in `src/dispatch/signal/redaction.py`. It calls the recursive `_redact`, which replaces any dict value whose key matches with `"[REDACTED]"` and recurses into nested dicts and lists.
- Matching is case-insensitive and exact on the key name. It is not a substring match, so `apiKey` and `x-api-key` are not masked. Keys are masked at any depth.
- Default keys come from `src/dispatch/config.py:98-102`: `password`, `secret`, `api_key`, `session_token`, `authorization`. Override with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable (comma-separated).

**Is the unmasked payload written to the database?**

Yes, in two places:

- **Initial insert:** `create_instance` plus the commit in the route store the raw payload unmasked (`views.py:121-127`, `service.py:680`). It stays unmasked until the processing loop runs, which can take up to about 60 seconds (`LOOP_DELAY = 60`).
- **Failure path:** if the flow raises before its first commit, `process_signal_batch` calls `rollback()` (`flows.py:403`). The in-memory masking is discarded, so the instance stays in the table with the raw payload unmasked. Since `case_id` and `filter_action` remain null, the loop will retry it on the next pass, and the failure will repeat until it succeeds or the row is removed. I did not confirm whether any path clears it.

On success, the redacted `raw` is persisted by the commit in `filter_signal` or in the entity step. So the unmasked copy is overwritten, not kept as a separate row. The masking is a replacement, not a second copy: the DB ends up with the redacted version.

**Also worth knowing**

The POST response is serialized from the instance after the commit, so it returns the unmasked `raw` as stored at that moment. Anyone with access to that response sees the sensitive values.

I did not change any code. I also did not run the tests or confirm the behaviour against a live database. The points about the rollback path and the response contents come from reading the code, not from running it.

----- next turn -----

The cause is commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2 Sep 2025). It added `[:1]` to the JSONPath lookup in `find_entities` (`src/dispatch/entity/service.py`), so only the first matching field produced an entity. The commit message says the change was for performance, but it dropped every match after the first.

**Fix:** I removed the `[:1]` slice and the comment that came with it. `find_entities` now keeps every match, as it did before the commit.

**Verification:** `python -m pytest tests/entity` failed before the fix (`test_find_entities_with_field_only`: `assert 1 == 2`). After the fix, all 11 tests pass. I did not change any tests.

The working tree also has the changes from earlier turns: the `delete_custom_event` permission restore, the new `tests/incident/` test, and the restricted-case filter fix in `src/dispatch/database/service.py`. I did not run the full test suite, and nothing is committed.

----- next turn -----

**Cause:** `find_entities` in `src/dispatch/entity/service.py` runs JSONPath on the raw payload without masking it. The masking that happens in `signal_instance_create_flow` (`flows.py:60`) doesn't cover the other callers. Entity types can also be extracted from already-stored instances in `entity_type/service.py:95` and `entity_type/flows.py:29`. When a JSONPath points at a masked key such as `session_token`, its value is `"[REDACTED]"`, which is still a string, so it becomes an entity. Every instance then gets the same `"[REDACTED]"` entity, and a deduplication filter on that entity type groups them into one case.

**Fix:** `find_entities` now runs `redact_raw` on the payload before it searches, and it skips any match whose value is `MASK`. The masking function and its key list are unchanged.

**Test:** `tests/entity/test_entity_redaction.py` is new. It puts a session token and a password in the payload, points entity types at both and at a visible field, and asserts that only the visible value becomes an entity. Against the code without this fix, the test fails. With the fix, it passes.

**Results:** `tests/entity`, `tests/signal` and `tests/entity_type` pass: 50 passed, 1 skipped. I did not change any existing tests.

**Working tree:** This change is on top of the earlier uncommitted edits (the `delete_custom_event` restore, the restricted-case filter fix, and the entity `[:1]` removal). Nothing is committed.

----- next turn -----

**Recap**

**Security review (permissions).** I listed every POST, PUT, PATCH and DELETE handler in the case and incident routers that had no `PermissionsDependency`. Five did. Three of them are open on purpose or were never protected: `create_case`, `create_case_channel` and `create_case_resources` in the case API, and `create_incident` in the incident API. I left those alone. The fifth, `delete_custom_event`, was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` dependency. I restored it in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views_permissions.py`, which fails if the check goes missing again. That test passes with the fix and fails against HEAD.

**Restricted cases visible to non-participants.** `restricted_case_filter` in `src/dispatch/database/service.py` had its participant check removed, so any non-admin user saw every restricted case. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") caused it. I restored the `and_` that requires the participant match, the same as the incident filter. The existing test `test_restricted_case_filter_with_test_data` fails against the old code and passes now.

**Entity extraction keeps only the first match.** Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath lookup. I removed it. `tests/entity` went from one failure to passing.

**Masked values becoming entities.** The masking itself was introduced in `d2675cf4` ("feat(signal): mask sensitive raw fields before processing"). It runs in the signal flow, but `find_entities` is also called on stored instances from `entity_type/service.py` and `entity_type/flows.py`, so masked fields could still become entities. A JSONPath pointing at a masked key yields `"[REDACTED]"`, and that shared value grouped unrelated instances. I moved the masking into `find_entities`, which now also skips matches equal to the mask. The masking function and key list are unchanged. I added `tests/entity/test_entity_redaction.py`, which fails without the fix and passes with it.

**Open items**
- Nothing is committed. The working tree has the changes above, plus the `[:1]` removal.
- I ran `tests/entity`, `tests/signal`, `tests/entity_type`, `tests/case`, `tests/incident` and `tests/database/test_service.py`. I did not run the full suite.
- `create_case_channel` and `create_case_resources` still have no permission check. They were never protected, so they are a separate decision.
- The unmasked payload is stored between the POST and the processing loop, and it stays there if processing fails before its first commit.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4