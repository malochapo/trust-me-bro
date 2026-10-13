Five endpoints change data without a `PermissionsDependency` in their route definition:

1. `src/dispatch/case/views.py:162`: `POST ""`, `create_case`
2. `src/dispatch/case/views.py:236`: `POST /{case_id}/resources/conversation`, `create_case_channel`
3. `src/dispatch/case/views.py:260`: `POST /{case_id}/resources`, `create_case_resources`
4. `src/dispatch/incident/views.py:117`: `POST ""`, `create_incident`
5. `src/dispatch/incident/views.py:503`: `DELETE /{incident_id}/event/{event_uuid}`, `delete_custom_event`

I only checked the route decorators in these two files. Neither router sets router-level `dependencies`, so these five are unprotected at the route level. I did not check how the routers are mounted in the app's API setup. No code was changed.

----- next turn -----

The one regression is `delete_custom_event` (`DELETE /{incident_id}/event/{event_uuid}`) in `src/dispatch/incident/views.py`. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line as part of a cleanup. The other two unprotected routes that change data, `create_case_channel` and `create_case_resources`, were added without a check and never had one, so I treated them as unchecked from the start, not regressions. `create_case` and `create_incident` are the intended open reporting endpoints.

**Changes (uncommitted):**
- `src/dispatch/incident/views.py`: restored the `IncidentEventPermission` dependency on `delete_custom_event`, exactly as it was before `28c21e1e`.
- `tests/incident/test_incident_event_permissions.py` (new): checks the DELETE route's declared dependencies and fails if `IncidentEventPermission` is missing. It inspects the router, so it doesn't need a database or a request.

**Verification:**
- The new test passes with the fix and fails when the fix is stashed.
- The case and incident event tests pass (5 passed).
- The full `python -m pytest` run gives 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. They fail the same way with my change stashed, so they predate it and I didn't touch them.

I ran the tests with the environment values from the CI workflow (`DATABASE_HOSTNAME=localhost`, `DATABASE_CREDENTIALS=dispatch:dispatch`, `DISPATCH_ENCRYPTION_KEY`). I set them only in the shell and did not write them to the repo.

----- next turn -----

The cause is in `restricted_case_filter` in `src/dispatch/database/service.py`. Members see every restricted case because the participant check is no longer attached to restricted cases.

**The bug:** the member-role filter had `Case.visibility == restricted` as its own OR term, next to `IndividualContact.email == current_user.email`. So any restricted case matched, whether or not the user was a participant.

**The commit:** `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). It replaced `and_(restricted, participant email matches)` with the two separate terms. The filter was originally correct, from `7931a1e6` ("Respect restricted case visibility") and `b05613b5`.

**The fix:** I restored the `and_` grouping, so a restricted case is visible only when the user is a participant. This is the only change, and no tests were modified.

**Verification:**
- `tests/database/test_service.py` passes (25 passed), including `test_restricted_case_filter_with_test_data`, which failed before the fix with "Member should see 3 cases … got 4".
- The full suite gives 361 passed, 4 skipped, 7 failed. The 7 failures are in `tests/ai/test_ai_service.py` and `tests/entity/test_entity_service.py`. They also fail without my changes, so they predate this work.
- I did not hit the cases list endpoint directly. The check is at the filter level, which the cases list uses through `search_filter_sort_paginate`.

Together with the earlier fix, this leaves two uncommitted changes: the restored `IncidentEventPermission` dependency and this filter fix, plus the new incident permission test.

----- next turn -----

Short answer: masking happens in `redact_raw` in `src/dispatch/signal/redaction.py`, but only after the instance has already been committed. The unmasked payload is written to the database during the POST, and nothing removes it from that original write.

**Trace of `POST /api/v1/{organization}/signals/instances`**

1. **Request handler** (`src/dispatch/signal/views.py`, `create_signal_instance`): resolves the project, then the signal definition by variant or external ID, falling back to the default definition. It calls `signal_service.create_instance` and then `db_session.commit()`. The raw payload is stored at this point with no masking. The handler returns the new `SignalInstanceRead`, which includes `raw`, so the caller also gets the unmasked payload back. Nothing is queued from the request.
2. **Storage** (`src/dispatch/signal/service.py:680`): `create_instance` does `raw=json.loads(json.dumps(...))`, a JSON round-trip with no redaction.
3. **Background processing**: the request does not open a case. A separate loop (`main_processing_loop` in `src/dispatch/signal/flows.py`, run by `dispatch signals process` in `cli.py`) picks up rows with `filter_action` and `case_id` both null, in batches of 500, and calls `signal_instance_create_flow`.
4. **Masking** (`src/dispatch/signal/flows.py:60`): the first step of `signal_instance_create_flow` is `signal_instance.raw = redact_raw(signal_instance.raw)`. Entity extraction runs after this, so it only sees masked values (`entity/service.py` reads `signal_instance.raw` through JSONPath).
5. **Entities and filtering**: entities are committed if any apply. `signal_service.filter_signal` runs snooze and dedup, then commits (`service.py:896`). Filtered instances return there, and that commit is also when the masked `raw` is first saved.
6. **Case creation** (if not filtered, not canary, and `create_case` is set): the case flow runs and opens or updates a case. I found no case code that reads `signal_instance.raw`.

**Masking function and defaults**

- `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` in `src/dispatch/signal/redaction.py`, with a recursive helper `_redact`.
- It replaces the value with `[REDACTED]` for any dict key whose lowercased name matches the list, at any depth, including inside lists. Other values are returned unchanged.
- Default keys come from `src/dispatch/config.py:98`, settable with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable: `password`, `secret`, `api_key`, `session_token`, `authorization`.
- Matching is exact after lowercasing. `apiKey` becomes `apikey`, which does not match `api_key`, so it is not masked. Neither are `token`, `api-key`, or secrets sitting inside a string value. I found no tests for `redact_raw`.

**Is the unmasked payload written to the database?** Yes. The POST handler commits the raw payload before any masking runs. The masked version overwrites the row later, in `filter_signal`'s commit. That leaves three gaps:

- The original unmasked value persists in the database's row history (dead tuples until vacuum), in the write-ahead log, and in any backups taken before the overwrite.
- If processing fails before `filter_signal` commits, the row stays unmasked. `process_signal_batch` rolls back on error, so anything not yet committed is discarded, but the POST's commit has already stored the unmasked payload.
- The POST response returns the unmasked payload to the caller.

The fix would be to call `redact_raw` before the POST's first commit, for example in `create_instance`, so the unmasked payload is never written. I have not changed any code, as you asked.

----- next turn -----

The change responsible is commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02). In `find_entities` (`src/dispatch/entity/service.py`), it changed `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. That keeps only the first match, so a JSONPath that matches several fields produces one entity instead of one per field.

**Fix:** I restored the original line and removed the comment that came with the commit. No tests were changed.

**Verification:**
- `tests/entity` passes (11 passed). `test_find_entities_with_field_only` was the failing test.
- The full suite gives 362 passed, 4 skipped, 6 failed. The 6 failures are the `TestGenerateReadInSummary` and `TestGenerateTacticalReport` tests in `tests/ai/test_ai_service.py`. They also failed before any of my changes, so they predate this work and I did not investigate them.

Uncommitted changes in the working tree now:
- `src/dispatch/incident/views.py`: restored the `IncidentEventPermission` check on `delete_custom_event`.
- `tests/incident/test_incident_event_permissions.py` (new): regression test for that check.
- `src/dispatch/database/service.py`: restored the participant check on restricted cases in `restricted_case_filter`.
- `src/dispatch/entity/service.py`: removed the `[:1]` truncation.

----- next turn -----

Analysts' grouping comes from a masked value turning into an entity. The signal flow replaces the token with the placeholder `[REDACTED]` before extracting entities (`src/dispatch/signal/flows.py:60`). The entity JSONPath then matches that placeholder string, so every instance of the signal gets an entity with the value `[REDACTED]`. The deduplication filter then groups every instance that has it. I did not run the deduplication path end to end, so the last step is inferred from the code. The masking commit `d2675cf4` ("feat(signal): mask sensitive raw fields before processing") is what put the placeholder in front of entity extraction.

**Fix** (`src/dispatch/entity/service.py`, `find_entities`):
- Entities are now extracted only from `redact_raw(signal_instance.raw)`. This applies wherever `find_entities` is called, including the entity-type paths in `entity_type/service.py` and `entity_type/flows.py`, which can run on payloads that were stored before masking existed.
- A match whose value equals `MASK` is skipped, because a JSONPath that points at a masked field still matches the placeholder string.
- `redact_raw` and the masking in the flow are unchanged.

**Test** (`tests/entity/test_entity_masking.py`, new): gives a payload with `session_token`, `password` and `user`, with an entity type for each. It asserts only `alice` is extracted, first on the raw payload and then on the redacted payload, the way the flow sees it. The test fails without the fix and passes with it.

**Full suite:** 363 passed, 4 skipped, 6 failed. The 6 failures are the `tests/ai/test_ai_service.py` tests that were already failing before my changes.

Uncommitted changes in the working tree:
- `src/dispatch/incident/views.py`: restored the `IncidentEventPermission` check on `delete_custom_event`.
- `tests/incident/test_incident_event_permissions.py` (new): test for that check.
- `src/dispatch/database/service.py`: restored the participant check in `restricted_case_filter`.
- `src/dispatch/entity/service.py`: removed the `[:1]` truncation, and added the redaction described above.
- `tests/entity/test_entity_masking.py` (new): masking test.

----- next turn -----

## Recap

**Unprotected data-changing routes (first review).** Five POST/PUT/PATCH/DELETE handlers had no `PermissionsDependency` on their route. Three are case routes and two are incident routes. Only `delete_custom_event` lost a check that it used to have. The other four were never protected: `create_case` and `create_incident` are the intended open reporting endpoints, and the two case resource routes were added without one.

**Restored check.** `incident.delete_custom_event` regained its `IncidentEventPermission` dependency. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed it. The new test `tests/incident/test_incident_event_permissions.py` fails if the check goes missing again. It fails without the fix and passes with it.

**Restricted cases visible to members.** `restricted_case_filter` in `src/dispatch/database/service.py` had `Case.visibility == restricted` as its own OR term, so any member saw every restricted case. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") caused it. The fix restores the `and_` that ties restricted visibility to participation. `tests/database/test_service.py` passes, including `test_restricted_case_filter_with_test_data`.

**Signal masking and the GitHub token signal.** The payload is masked in `redact_raw` (`src/dispatch/signal/redaction.py`) during signal processing (`src/dispatch/signal/flows.py:60`). Masking runs after the instance is committed, so the unmasked payload is written to the database during the POST. Masked values were also reaching entity extraction. The flow replaced the token with `[REDACTED]`, the entity JSONPath matched that placeholder, and every instance of the signal got the same entity, which the deduplication filter then grouped. The fix is in `find_entities` (`src/dispatch/entity/service.py`): entities are extracted only from the redacted payload, and the placeholder value is skipped. The new test `tests/entity/test_entity_masking.py` covers both the raw and redacted payloads.

**Entity extraction returning only the first match.** Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]`, so only one entity per JSONPath was extracted. I removed the truncation, and `tests/entity` passes.

**Test status.** The full suite gives 363 passed, 4 skipped and 6 failed. The 6 failures are in `tests/ai/test_ai_service.py`, which were failing before any of these changes. I did not investigate them.

**Open items.** Nothing is committed. The changes are in the working tree: the incident permission restore and its test, the restricted-filter fix, the entity fix and its test. Two items are not fixed: the POST still stores the unmasked payload before masking runs, and the masking key list only matches exact names, so `apiKey` and `token` are not masked. You asked me to leave masking as it is, so I did not change either.

```
UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4
```