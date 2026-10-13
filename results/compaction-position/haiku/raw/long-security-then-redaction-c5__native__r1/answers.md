Five write routes have no `PermissionsDependency` in their route definition: three in the case API and two in the incident API.

**Case API (`src/dispatch/case/views.py`)**
- `POST /` (`create_case`, line 162)
- `POST /{case_id}/resources/conversation` (`create_case_channel`, line 236)
- `POST /{case_id}/resources` (`create_case_resources`, line 260)

**Incident API (`src/dispatch/incident/views.py`)**
- `POST /` (`create_incident`, line 117)
- `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`, line 503)

I checked the full decorator blocks for these five, and neither router is built with router-level dependencies (`APIRouter()` in both files). The grep also found no `PermissionsDependency` in the function parameters. Any authorization for these routes would have to be inside the function bodies, which this check does not cover. No code was changed.

----- next turn -----

I restored the missing check on `delete_custom_event` and added a test that fails when it's absent. It passes now.

**The regression:** `DELETE /{incident_id}/event/{event_uuid}` in `src/dispatch/incident/views.py` lost its `IncidentEventPermission` dependency in commit `28c21e1e` ("refactor(incident): tidy custom event routes"). That commit only removed that one line. The case API's equivalent route still has `CaseEventPermission`, and the other incident event routes still have their checks.

**The fix:** I restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on that route. The `src/dispatch/incident/views.py` diff is that one added line.

**The test:** `tests/incident/test_incident_event_views.py` looks up the DELETE route on the incident router and asserts that `IncidentEventPermission` is in its dependencies. The existing event tests call view functions directly, which skips route dependencies, so they could not catch this. I ran the new test before restoring the check and it failed, then ran it after and it passed. `python -m pytest tests/incident/test_incident_event_views.py tests/case/test_case_event_views.py` gives 5 passed. I did not run the full suite.

**The other write routes:**
- `POST /` on the case and incident APIs: left open, as you said.
- `POST /{case_id}/resources/conversation` (`create_case_channel`): I found no sign it ever had a check. It was added in `ced74f33` without one. This is a judgement from the history, not a confirmed design decision, so you may want to check it.
- `POST /{case_id}/resources` (`create_case_resources`): I did not trace its history, so I can't say whether it was ever guarded. The history I checked doesn't show a removal.

----- next turn -----

The cause was a regression in the case search filter, and I've restored the check. It was introduced by commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, Sep 2 2025).

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` decides which cases a member can see in the list. The security fix `b05613b5` had written it as "open, or restricted and the user is a participant". The flatten commit split the `and_` into two separate `or_` terms, so `Case.visibility == Visibility.restricted` matched on its own. Any member could then see every restricted case. The incident filter was not affected and still has the `and_`.

**Fix:** I put the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` back. That is the only change in that file, and it matches the incident filter.

**Verification:** `python -m pytest tests/database/test_service.py tests/case/test_case_service.py` gives 35 passed. I did not change any existing tests. I also did not add a test for this bug, and I did not run the list endpoint against a restricted case as a non-participant. Because the existing tests pass both with and without the fix, they do not cover this path. Adding a test for it would be a sensible follow-up if you want one.

**Also in the working tree from earlier:** the incident `delete_custom_event` permission restore and the new `tests/incident/` test are still uncommitted.

----- next turn -----

The unmasked payload is written to the database. Masking happens later, in a background worker, so it is not applied before the first commit. This is from reading the code; I did not run it.

**Path of a request**

1. **Route:** `create_signal_instance` in `src/dispatch/signal/views.py:70-120`. It resolves the signal definition, calls `signal_service.create_instance`, and commits (around line 127). It never calls the redaction code, and its `background_tasks` parameter is unused.
2. **Storage:** `create_instance` in `src/dispatch/signal/service.py:650-712` copies `raw` into the new row (`json.loads(json.dumps(...))`) and adds it to the session. The view's commit writes the **unmasked** payload to the `SignalInstance.raw` JSONB column.
3. **Processing:** a separate worker (`src/dispatch/cli.py` around lines 960-1010, and `signal/flows.py` around 415-428) selects instances with `filter_action IS NULL` and `case_id IS NULL`, then calls `signal_instance_create_flow`.
4. **Masking:** the first step in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:59-60`) is `signal_instance.raw = redact_raw(signal_instance.raw)`. Entity extraction runs on the masked copy.
5. **Filtering:** `signal_service.filter_signal` (`service.py:866`) applies snooze and deduplication. It commits and sets `filter_action`. If that is set, the flow returns early.
6. **Case creation:** if the signal is not filtered and `create_case` is set, the flow opens or updates a case. Canary instances return before this step.

**Where masking happens:** `redact_raw` in `src/dispatch/signal/redaction.py:10-27`. It returns a new structure with every dict key whose lowercased name is in the configured set replaced by `"[REDACTED]"`. It recurses into dicts and lists, matches keys exactly after lowercasing, and leaves other values alone.

**Default keys:** `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98-102`, default `password,secret,api_key,session_token,authorization`. Keys like `token`, `access_token`, `client_secret`, or `apiKey` are not matched, because matching is exact and `apikey` is not `api_key`.

**Is the unmasked payload persisted?** Yes, in two ways:

- **Between the API commit and the worker run.** The row holds the raw payload, and the masking is only in memory until the worker commits.
- **If processing never succeeds.** `filter_signal`'s commit is what stores the masked version. If the flow raises before that commit (for example in entity extraction or case creation), the worker rolls back, and the row keeps the unmasked payload. A row that keeps failing stays unmasked indefinitely. This is a reading of the code, not something I reproduced.

The API response is also built from the unmasked row, so the caller gets the unmasked payload back. The caller sent it, so this is not a new disclosure to that caller, but it is worth knowing.

**Suggested fix (not applied):** call `redact_raw` in `create_instance` before the `SignalInstance` is built, so the raw payload is masked on its first write. That would also cover the rollback case.

----- next turn -----

The cause is commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, Sep 2 2025). It changed `_find_entities_by_jsonpath_expression` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`, so each JSONPath entity type could only produce one entity.

**Fix:** I reverted that line to `matches = jpath.find(signal_instance.raw)`. That is the only change in the file.

**Verification:** `python -m pytest tests/entity` gives 11 passed. I did not run that suite before the change, so I can't confirm it was the cause of the red CI from the test output alone. The reversal restores the behaviour the code had before that commit.

**Working tree:** the earlier uncommitted changes are still there: the restored `delete_custom_event` permission in `src/dispatch/incident/views.py`, the restricted-case filter fix in `src/dispatch/database/service.py`, and the new `tests/incident/` test. I have not committed anything.

----- next turn -----



----- next turn -----

Masked values now never become entities. The fix is in `find_entities`, and the entity and signal tests pass (44 passed, 1 skipped).

**Why instances were grouped:** the `session_token` key is one of the default masked keys, so `redact_raw` replaces its value with the literal `"[REDACTED]"`. The JSONPath for "GitHub: Personal access token exposed" then matched that placeholder and created an entity with the value `[REDACTED]`. Every such instance got that same entity, and the deduplication filter on that entity type grouped them. I inferred this from the code. I did not reproduce it through the dedup filter.

**Second leak:** `entity_type/service.py` calls `find_entities` on stored instances when an entity type is added to a case. Those stored payloads are not redacted until the worker runs, so the real token became an entity value in that path. The new test reproduces this with an unmasked payload.

**Changes:**
- `src/dispatch/entity/service.py`: `_find_entities_by_jsonpath_expression` now runs `redact_raw` on the payload before matching. It also skips any string match equal to `MASK`. This covers both the normal flow and the recalculation path. `redact_raw`, `MASK`, and the default keys are unchanged.
- `tests/entity/test_entity_service.py`: added `test_find_entities_never_creates_entity_from_masked_value`. It checks that a `session_token` value creates no entity, and that an unmasked `user` value from the same payload still does. It failed before the fix (`assert 1 == 0`) and passes after.

The regex branch of `entity_type_pairs` is never used for extraction in this file, so only the JSONPath path needed the change.

Nothing is committed. Your earlier uncommitted changes are still in the working tree.

----- next turn -----

## Recap: authorization review and signal/entity fixes

**Authorization review (case and incident write routes)**
- Five write routes had no `PermissionsDependency` at HEAD: three in the case API and two in the incident API.
- `create_case` and `create_incident` are open on purpose, since anyone may report a case or incident.
- `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") dropped its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_event_views.py`, which fails if the check goes missing. Before the fix it failed with `assert IncidentEventPermission in []`.
- `create_case_channel` and `create_case_resources` are unprotected too, but I have not decided whether they are design choices or regressions. The origin of `create_case_resources` is untraced.

**Restricted case visibility**
- Members could see restricted cases they were not part of. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_` that required participation. The earlier security fix `b05613b5` (#6155) had the correct form. I restored it in `restricted_case_filter`, in `src/dispatch/database/service.py`. Its test suite passes, but I have not added a regression test for it.

**Signal instance masking**
- Masking happens in `signal_instance_create_flow`, through `redact_raw` in `src/dispatch/signal/redaction.py`. The masking was introduced by `d2675cf4`.
- Default masked keys are `password`, `secret`, `api_key`, `session_token`, and `authorization`. Matching is exact and case-insensitive, so keys such as `token` or `client_secret` are not masked.
- The unmasked payload is written to the database. The API commits the raw payload before the worker redacts it, and it stays unmasked if processing fails. **This gap is not fixed.** I suggested redacting before the first commit, and you have not asked for that yet.

**Entity extraction**
- Extraction kept only the first match because of `beb60cc4` ("perf(entity): stop at the first JSONPath match"). I reverted it, and `tests/entity` passes. I did not reproduce the red CI state before the fix.
- Masked values could also become entities. `find_entities` now redacts the payload before matching and skips the `[REDACTED]` placeholder. This closes the path behind "GitHub: Personal access token exposed" grouping unrelated instances. I added `test_find_entities_never_creates_entity_from_masked_value`, which failed before the fix. `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**Working tree:** all changes are uncommitted: `src/dispatch/database/service.py`, `src/dispatch/entity/service.py`, `src/dispatch/incident/views.py`, `tests/entity/test_entity_service.py`, and the new `tests/incident/`.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4