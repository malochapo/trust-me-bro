Five write endpoints have no `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""`: `create_case`, line 162
2. `POST /{case_id}/resources/conversation`: `create_case_channel`, line 236
3. `POST /{case_id}/resources`: `create_case_resources`, line 260

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""`: `create_incident`, line 117
5. `DELETE /{incident_id}/event/{event_uuid}`: `delete_custom_event`, line 503

`create_incident_resources` (line 163) is not on the list because it declares `IncidentViewPermission`. Neither file sets router-level dependencies (`APIRouter()` at lines 61 and 59), so these five routes have no permission check at the route level. I did not check whether a global middleware or app-level dependency enforces auth on them. I made no code changes.

----- next turn -----

Only one of the five is a regression: the incident `DELETE /{incident_id}/event/{event_uuid}` route (`delete_custom_event`). I restored its check and added a test that fails when the check is missing. The test passes with the fix and fails without it.

The other four look like design choices:
- `create_case` and `create_incident` are the open reporting endpoints you described.
- `create_case_channel` and `create_case_resources` were added without a check in `ced74f33` and `f08a22b3`. Nothing removed one, so I'd treat them as unguarded from the start rather than regressions. You may still want to confirm that's intended.

**The regression:** commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, 2025-07-14) deleted `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from the route. The commit message doesn't mention permissions. The route was originally added without a check in `319b2faf`, and the check was added later. The other incident custom event routes still have `IncidentEventPermission`, so this looks like an accidental deletion.

**Changes:**
- `src/dispatch/incident/views.py`: restored the `dependencies=` line on the delete route. No other lines changed.
- `tests/incident/test_incident_views.py` (new): `test_delete_custom_event_requires_incident_event_permission` finds the DELETE route on the incident router and asserts that `IncidentEventPermission` is among its `PermissionsDependency` classes. It checks the route definition rather than making a request, so it doesn't depend on auth setup.

**Test run:** `python -m pytest tests/incident/test_incident_views.py` gives 1 passed with the fix. With the fix temporarily stashed, it gives 1 failed. I did not run the full suite.

----- next turn -----

The cause is in `restricted_case_filter` (`src/dispatch/database/service.py`). It put `Case.visibility == Visibility.restricted` into the `or_` by itself, so every restricted case passed the filter whether or not the user was a participant. The incident version of the filter pairs that condition with the participant email check. I restored that pairing in the case version.

**Introducing commit:** `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). It removed the `and_(...)` wrapper, which was added in `b05613b5` (the #6155 authz hardening). The commit title describes a refactor, but it changed behaviour.

**Change:** the restricted branch is wrapped in `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` again. No other lines changed, and I did not touch any tests.

**Verification:**
- `tests/database/test_service.py` and `tests/case/test_case_service.py`: 35 passed with the fix.
- Without the fix, `test_restricted_case_filter_with_test_data` fails, so the existing test does catch this. The filter is applied to the cases list through `search_filter_sort_paginate`, so this covers the reported symptom.
- I did not run the API endpoint directly with a member user.

----- next turn -----



----- next turn -----

**Short answer:** Masking happens in a background worker, not in the POST handler. The handler commits the raw payload unmasked, so the unmasked payload is written to the database. It is overwritten with the masked version only when the worker processes the row successfully. No code was changed.

**The path, step by step**

1. **Route:** `POST /instances` in `src/dispatch/signal/views.py:70` (`create_signal_instance`). It resolves the project, then the signal definition by `externalId`/`variant`, falling back to the default. `background_tasks` is a parameter but is never used.
2. **Persist:** the handler calls `signal_service.create_instance` (`src/dispatch/signal/service.py:650`). That stores `raw=json.loads(json.dumps(...))` (line 680) with no masking, and the view then calls `db_session.commit()` (`views.py:~117`). **This is the first time the unmasked payload reaches the database.** The response (`SignalInstanceRead`, which includes `raw`) also returns it to the sender.
3. **Processing:** nothing in the POST path calls the flow. A worker picks up rows with `filter_action IS NULL` and `case_id IS NULL`, oldest first, up to 500 at a time (`signal/service.py:900`, `cli.py:~985`). The worker is the `dispatch signals process` command (`cli.py:938`). It calls `signal_flows.signal_instance_create_flow` (`signal/flows.py:46`) and commits after each instance.
4. **Masking:** `signal_instance_create_flow` runs `signal_instance.raw = redact_raw(signal_instance.raw)` (`flows.py:60`) before entity extraction. The function is `redact_raw` in `src/dispatch/signal/redaction.py`.
5. **Entities:** `entity_service.find_entities` runs on the masked payload (`entity/service.py:290` uses JSONPath on `signal_instance.raw`). Entities whose match lives under a masked key cannot be extracted. The commit at `flows.py:75` only runs when entity types exist.
6. **Filter:** `signal_service.filter_signal` (`signal/service.py:866`) applies snooze and then dedup, and always commits (line 896). Filtered instances return here. This commit also persists the masked `raw`.
7. **Case:** canary instances and signals with `create_case` false return after step 6. Otherwise the flow resolves the case type, priority, oncall and conversation target, then calls `case_service.create` and commits (`flows.py:~188–191`).

**Default masked keys**

`SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98` defaults to `password,secret,api_key,session_token,authorization`, overridable by env var. Matching is:
- exact key name, case-insensitive (`str(key).lower()`), so `API_KEY` matches and `apiKey`, `x-api-key` or `token` do not;
- at any depth inside nested dicts and lists;
- not applied to string values, so a JSON string containing a password is not masked.

The replacement value is `"[REDACTED]"`.

**Is the unmasked payload written to the database?** Yes, in two ways:
- **Always, briefly:** at the POST commit, until the worker processes the row. The window is up to the worker's loop interval plus backlog.
- **Persistently, if processing fails:** `process_signal_batch` and the CLI loop roll back on exception (`flows.py:403`). That leaves the unmasked `raw` in place, and the row is retried on the next pass. The repo has no test that checks masking, and I did not look for a retention or purge job.

**Not checked:** whether the created case, Slack messages or the case's stored data copy `raw` from the instance, and whether anything else uses the unmasked value before step 4. `flows.main_processing_loop` (`flows.py:441`) has no caller in `src/`, so I could not tell which deployment runs it.

----- next turn -----

Entity extraction is fixed. All 11 tests in `tests/entity` pass. The existing tests are unchanged.

**Cause:** commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega) changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`. That slice keeps only the first match, so a JSONPath like `asset[*].id` produced one entity instead of one per field. The commit is dated 2025-09-02, not this week. It is the only change to that line in the history, so it is the one that broke the test.

**Fix:** I removed the `[:1]` slice and its comment, so the line is `matches = jpath.find(signal_instance.raw)` again. This reverts the behaviour the commit intended to change, so the performance gain is gone. If the speed-up matters, the next step is a cap that applies only to JSONPaths without wildcards, but that is a design choice for you, and I did not make it.

**Verification:** `python -m pytest tests/entity -q` gives 11 passed. Before the fix, `test_find_entities_with_field_only` failed with `assert 1 == 2`.

The changes from earlier in this session are still uncommitted in the working tree, alongside this one.

----- next turn -----

Masked values no longer become entities, so instances with masked tokens stop grouping together. All 52 tests in `tests/signal`, `tests/entity` and `tests/entity_type` pass, with 1 skipped. The masking itself is unchanged.

**Why they were grouped:** the signal flow masks `raw` in memory, so the token becomes `"[REDACTED]"` before `find_entities` runs. That string passed the `isinstance(str)` check, so every instance got the same entity value `"[REDACTED]"`. The deduplication filter on that entity type then treated all of them as the same thing. The other two extraction paths, `entity_type/service.py` and `entity_type/flows.py`, read `raw` straight from the database, where an unprocessed row can still hold the real token, so they could also extract it.

**Fix** (`src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression`): the JSONPath now runs against `redact_raw(signal_instance.raw)`, and a match whose value is the mask marker is skipped. Because the change sits inside `find_entities`, every caller gets it.

**Test:** `tests/entity/test_entity_masking.py` has three tests:
- a masked session token yields no entity;
- two instances with different masked tokens yield no entities, so nothing can group them;
- unmasked values are still extracted alongside a masked one.

With the masking logic disabled, all three fail. With the fix in place, the entity suite passes (14 tests).

**Not changed:** `src/dispatch/entity_type/flows.py:29` assigns the result of `.append(...)` to `entity_types`, which is `None`, so that code path looks broken. I did not touch it because it is outside this bug.

**Still uncommitted:** the earlier `[:1]` revert in the same file and the other changes from this session are still in the working tree.

----- next turn -----

## Recap

**Investigation 1: unguarded write routes and the incident delete regression**

Before my changes, five data-changing handlers in the case and incident routers had no `PermissionsDependency`. Four are intentionally open, since anyone may report a case or incident. `delete_custom_event` was a regression. Commit `28c21e1e` dropped its `IncidentEventPermission` check. I restored the check in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views.py`, which fails if the check is removed. I confirmed it fails without the fix and passes with it.

**Investigation 2: restricted cases visible to non-participants**

The cases list showed restricted cases to users who were not participants. The cause was `restricted_case_filter` in `src/dispatch/database/service.py`. The restricted-visibility condition had lost its `and_` wrapper, so any restricted case passed the filter. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the wrapper, even though its title describes a refactor. I restored the wrapper. `tests/database/test_service.py` and `tests/case/test_case_service.py` pass with the fix (35 tests). The existing test `test_restricted_case_filter_with_test_data` fails without it.

**Investigation 3: signal payload masking and entity extraction**

- **Masking path:** `POST /api/v1/{organization}/signals/instances` stores the raw payload and commits it before any masking. A background worker later runs `signal_instance_create_flow`, which masks the payload in memory. Masking is done by `redact_raw` in `src/dispatch/signal/redaction.py`. The default masked keys are `password,secret,api_key,session_token,authorization`. The unmasked payload is written to the database at the POST commit and stays there if processing fails. The masking was introduced by `d2675cf4`.
- **Entity extraction bug:** commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath match, so only the first match became an entity. I reverted that line.
- **Masked values as entities:** the masked value `"[REDACTED]"` could become an entity. Instances with masked tokens then shared that entity value and were grouped together by the deduplication filter. Extraction now runs against the redacted payload and skips mask-marker values. The fix is in `src/dispatch/entity/service.py`. The new tests are in `tests/entity/test_entity_masking.py`. They fail when masking is disabled and pass with the fix.

**Test status:** `tests/signal`, `tests/entity` and `tests/entity_type` pass (52 passed, 1 skipped). I did not run the full suite.

**Open items:**
- `src/dispatch/entity_type/flows.py:29` appears broken: it assigns the result of `.append(...)` to `entity_types`, which is `None`. I did not change it.
- All changes are uncommitted in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4