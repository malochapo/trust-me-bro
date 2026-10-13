Four mutating routes don't declare a `PermissionsDependency` in their route definition:

1. `POST /incident/` (`create_incident`), `src/dispatch/incident/views.py:117`
2. `POST /case/` (`create_case`), `src/dispatch/case/views.py:162`
3. `POST /case/{case_id}/resources/conversation` (`create_case_channel`), `src/dispatch/case/views.py:236`
4. `POST /case/{case_id}/resources` (`create_case_resources`), `src/dispatch/case/views.py:260`

Both routers are plain `APIRouter()` with no router-level dependencies, so these four have no permission check at the route level. I didn't check whether the handlers enforce authorization internally, since your question was about route declarations. No code was changed.

----- next turn -----

I found no regression, so I made no code changes and wrote no test.

The two case routes that look unintentionally open are `create_case_channel` (`POST /case/{case_id}/resources/conversation`, `src/dispatch/case/views.py:236`) and `create_case_resources` (`POST /case/{case_id}/resources`, `src/dispatch/case/views.py:260`). Git history shows neither ever had a `PermissionsDependency`:

- `create_case_resources` was added in `f08a22b3` (#3791) with no dependency.
- `create_case_channel` was added in `ced74f33` (#5207) with no dependency.
- `git log -L` on both decorator ranges shows no removed lines.

The handlers don't check permissions internally either. The only guard is `get_current_case` (`src/dispatch/case/views.py:64`), which returns 404 for a missing case and does nothing else. So any caller who can reach the API can trigger these routes for any case ID. They were never gated, so this is a missing check rather than a regression.

The other two open routes are the intended report endpoints: `create_case` and `create_incident`.

To close the two gaps, I'd add `dependencies=[Depends(PermissionsDependency([CaseEditPermission]))]` to both routes, plus a test that fails if it's removed. Which permission to use is your call. I'd suggest `CaseEditPermission`, which the other mutating case routes use, but `CaseViewPermission` is also possible if these are meant to be read-only resource creation. Tell me which you want and I'll make the change and run `python -m pytest`.

----- next turn -----

Security team's report is confirmed and fixed. The restricted cases list let users see restricted cases they weren't participants in. The commit that introduced it is `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02).

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` lost the `and_` wrapper. The `or_` had a bare `Case.visibility == Visibility.restricted` clause, so every restricted case matched for any non-admin role. The incident version of the filter still requires participation.

**Fix:** I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` clause, matching the incident filter. The diff is 4 lines in `service.py`.

**Verification:**
- `tests/database/test_service.py::test_restricted_case_filter_with_test_data` fails without the fix and passes with it. That existing test catches this regression, so I added no new test and changed no tests.
- `tests/database/test_service.py` and `tests/case` pass (40 passed).
- The full suite gives 360 passed, 4 skipped, 7 failed. The 7 failures are in `tests/ai` and `tests/entity` and also fail with my change stashed, so they predate this fix. I didn't investigate them.

----- next turn -----



----- next turn -----

The raw payload is masked in `signal_instance_create_flow`, not at the API. Between the API write and that masking step, the unmasked payload is committed to the database.

**1. API entry: `POST /api/v1/{organization}/signals/instances`** (`src/dispatch/signal/views.py:70-127`, `create_signal_instance`)
- It resolves the project and the signal definition (by `externalId`/`variant`, falling back to the default).
- It calls `signal_service.create_instance` (`src/dispatch/signal/service.py:650`) and then `db_session.commit()` at line 120.
- `create_instance` stores `raw` as-is, after a JSON round-trip. Nothing is masked here.
- The route does not call the processing flow. It returns the instance, which still holds the unmasked `raw`, so the response echoes the payload back to the caller.
- The `background_tasks` parameter is not used for this route.

**2. Processing: `process_signal_batch` → `signal_instance_create_flow`** (`src/dispatch/signal/flows.py`)
- Unprocessed instances are those with `filter_action IS NULL` and `case_id IS NULL` (`signal/service.py:900`). They are picked up by `process_organization_signals`, which is run by the `process_signals` command in `src/dispatch/cli.py:938`. I did not check how that command is scheduled.
- **Masking happens at `flows.py:60`:** `signal_instance.raw = redact_raw(signal_instance.raw)`, with the comment "mask sensitive values before entities are extracted from the payload". Entity extraction runs on the masked copy.
- Then, depending on the path, the instance is committed (in `find_entities`' block, or in `filter_signal`, which commits at `signal/service.py:896`). Filtering (snooze, dedup) happens in `filter_signal` (`signal/service.py:866`). If filtered, the flow returns there. Otherwise a case is created with `visibility=Visibility.open` and `case_service.create`.
- Canary instances, instances whose signal has `create_case=False`, and instances already handled by a filter action are stored and returned without opening a case.

**3. The masking function: `redact_raw` in `src/dispatch/signal/redaction.py`**
- Recursively walks dicts and lists and replaces the value of any key whose lowercased name is in the configured set with `"[REDACTED]"`. Scalars are returned unchanged.
- Matching is on key names only. Values are not inspected, and a masked key's whole subtree is replaced.
- Default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98-102`: `password, secret, api_key, session_token, authorization`.
- The env var replaces the default list rather than extending it.
- Keys such as `token`, `cookie`, or `private_key` are not masked by default.

**4. Is the unmasked payload written to the database? Yes, briefly.**
- The API commit at `views.py:120` persists the raw payload exactly as received, with secrets included.
- It is overwritten only when the processing flow later commits the redacted copy.
- If processing fails before that point, the unmasked payload stays in the database. `process_signal_batch` rolls back only uncommitted work, and the API commit has already happened.
- Instances that are never processed (for example, if the processing command isn't running) keep the unmasked payload indefinitely.

This is a static trace from reading the code. I did not run the endpoint or the tests, and I made no code changes.

----- next turn -----

The entity bug is fixed. The cause was commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02). It added `[:1]` to the JSONPath lookup in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`), so only the first match ever became an entity. I removed the slice and left the rest of the loop unchanged. No tests were modified.

**Verification:**
- `tests/entity` and `tests/signal`: 43 passed, 1 skipped. `test_find_entities_with_field_only` was failing before and now passes. I had set it aside earlier as unrelated, and it was the entity-side symptom of this bug.
- Full suite: 361 passed, 4 skipped, 6 failed. All 6 failures are in `tests/ai/test_ai_service.py`. They fail because the tiktoken encoding can't be downloaded (no network access in this environment). They are not related to this change.

The `[:1]` was added for performance, and I removed it without replacing it. A JSONPath with wildcards or filters can match many fields, so the scan now yields every match. If the performance concern still matters, it should be solved another way, for example by capping matches per entity type.

I didn't add a regression test for this. You didn't ask for one, and the existing `test_find_entities_with_field_only` already fails if the slice comes back.

The working tree also still has the earlier `src/dispatch/database/service.py` change, which is not committed.

----- next turn -----

Masked values can no longer become entities, no matter which code path extracts them. The added test fails when the fix is removed and passes with it.

**Why it happened:** The flow masks the payload at `signal/flows.py:60` before extracting entities, so the token's entity value became the literal string `"[REDACTED]"`. Every instance of this signal therefore produced the same entity, and the deduplication filter on that entity type grouped them into one case. The same problem applied to `entity_type/service.py:95`, which re-runs extraction on stored instances. Those can still hold unmasked payloads, because the API commit happens before the flow masks anything (see my earlier trace).

**Fix** (`src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression`):
- The function now runs `redact_raw` on the payload itself before applying the JSONPath, so extraction never sees unmasked values.
- Matches whose value equals `MASK` are skipped.
- The masking in `flows.py` is unchanged, as requested.

**Test:** `test_find_entities_never_extracts_masked_values` in `tests/entity/test_entity_service.py`. It covers a direct path, a list wildcard, and a recursive `$..` expression onto masked keys, and checks that an unmasked field still becomes an entity. No existing tests were changed.

**Verification:**
- The new test fails with the masking disabled and passes with it.
- Full suite: 362 passed, 4 skipped, 6 failed. The 6 failures are the same tiktoken network failures in `tests/ai/test_ai_service.py` as before.

**Still open:** The analysts' existing entities and case groupings are not repaired by this change. Entities already created with the value `"[REDACTED]"` remain in the database and would need a cleanup, which I did not run.

Uncommitted changes: `src/dispatch/database/service.py` (from the earlier restricted-case fix), `src/dispatch/entity/service.py`, and `tests/entity/test_entity_service.py`.

----- next turn -----

## Recap

**Restricted cases visible to non-participants.** Members of the security team could see restricted cases they were not part of. The cause was commit `42699ebc`, which flattened `restricted_case_filter` in `src/dispatch/database/service.py`. It dropped the `and_` that requires participation for restricted cases, so every restricted case matched for non-admin roles. I restored the clause, matching the incident filter. The existing test `test_restricted_case_filter_with_test_data` fails without the fix and passes with it.

**Permission review.** The review first found no regression, and that was wrong. A later scan turned up `DELETE /incident/{incident_id}/event/{event_uuid}`, whose `IncidentEventPermission` check was removed by `28c21e1e` ("refactor(incident): tidy custom event routes", 2025-07-14). I restored the check. The new test `tests/incident/test_incident_event_permissions.py` fails without it. The earlier review had also missed `create_case` and `create_incident`, which are open by design. Still open: the two case resource routes (`create_case_channel`, `create_case_resources`) are unprotected, and which permission to add is undecided.

**Signal payload masking.** A signal instance's raw payload is masked by `redact_raw` in `src/dispatch/signal/redaction.py`, which runs in the signal flow before entity extraction. The default keys are listed below. The API commits the unmasked payload before processing, so the unmasked payload does reach the database until the flow overwrites it. Masking was introduced in `d2675cf4`.

**Entity extraction keeps only the first match.** Commit `beb60cc4` added `[:1]` to the JSONPath lookup, so only one value per entity type became an entity. I removed the slice, which fixes `test_find_entities_with_field_only`.

**Masked values becoming entities.** Every instance of the "GitHub: Personal access token exposed" signal produced the same entity, the literal `"[REDACTED]"`, so the deduplication filter grouped them into one case. `find_entities` now masks the payload itself and skips masked values. The new test `test_find_entities_never_extracts_masked_values` fails without the fix. Entities already stored with the value `"[REDACTED]"` are not cleaned up.

**Verification:** Full suite: 363 passed, 4 skipped, 6 failed. The 6 failures are in `tests/ai`, caused by tiktoken being unable to download its encoding (no network). They predate this work. Nothing is committed. Uncommitted changes: `src/dispatch/database/service.py`, `src/dispatch/entity/service.py`, `src/dispatch/incident/views.py`, `tests/entity/test_entity_service.py`, and the new `tests/incident/`.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4