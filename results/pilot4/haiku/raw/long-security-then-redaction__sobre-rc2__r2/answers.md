Five mutating routes have no `PermissionsDependency` declared in their route definition:

**Case API (`src/dispatch/case/views.py`)**
- `POST /case` (`create_case`, line 162)
- `POST /case/{case_id}/resources/conversation` (line 236)
- `POST /case/{case_id}/resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
- `POST /incident` (`create_incident`, line 117)
- `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`, line 503)

Neither router is built with router-level dependencies (`APIRouter()` at `case/views.py:61` and `incident/views.py:59`), so nothing is applied globally. I didn't check whether these handlers enforce permissions inside the function body, so the list is about the route declarations only. No code was changed.

----- next turn -----

Yes, one of them is a regression: `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`). I restored its check and added a test that fails if it goes missing again. I did not commit anything.

**What happened**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, 2025-07-14) removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]`. It was the commit's only change, and a refactor shouldn't change behaviour, so this looks accidental.
- Before that, the route was guarded by `IncidentEventPermission` (since `328359b5`, which narrowed it from `IncidentCommanderOrScribePermission`). That permission allows organization admins, incident commanders, scribes, and reporters.

**Changes**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on the route.
- `tests/incident/test_incident_views_permissions.py` (new): finds the DELETE route on the incident router and asserts `IncidentEventPermission` is among its declared dependencies. I checked it by removing the line temporarily, where it failed with `assert IncidentEventPermission in []`, then restoring it.

**Test run**
- `python -m pytest tests/case tests/incident`: 16 passed.
- I didn't run the full suite.
- My first version imported `dispatch.main` through the `testapp` fixture and produced a database teardown error (`database "dispatch-test" is being accessed by other users`). Importing the incident router directly avoided it. I didn't find the root cause, and I haven't checked whether the error occurs elsewhere in the suite.

The other mutating routes I flagged earlier (`POST /case`, `POST /case/{id}/resources`, `POST /case/{id}/resources/conversation`, `POST /incident`) stay open, as you described. I did not check whether they're intentionally open in the same way.

----- next turn -----

The cause is in `restricted_case_filter` in `src/dispatch/database/service.py`, and I've fixed it. The commit that introduced it is `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02).

**Cause**
The flattening removed the `and_` that tied the restricted-visibility check to participation. The filter became:

```python
Case.visibility == Visibility.open,
Case.visibility == Visibility.restricted,   # matches every restricted case
IndividualContact.email == current_user.email,
```

So any non-admin user, whether or not they were a participant, got every restricted case in the list. The incident version of this filter still has the correct grouping.

**Fix**
I restored the grouping in `restricted_case_filter`, so restricted cases match only when the current user is a participant:

```python
Case.visibility == Visibility.open,
and_(
    Case.visibility == Visibility.restricted,
    IndividualContact.email == current_user.email,
),
```

**Verification**
- `python -m pytest tests/database/test_service.py tests/case -q`: 40 passed.
- With the fix reverted, `test_restricted_case_filter_with_test_data` fails, so the existing test covers this regression.
- I didn't change any tests.

**Working tree**
This fix is uncommitted, and the working tree also still has the earlier incident-route change and the new `tests/incident/` test from the previous step. I haven't committed anything.

----- next turn -----



----- next turn -----

The POST route stores the raw payload unmasked. Masking happens later, in a separate background step, and the masked version only overwrites the stored payload when that step runs and commits. Nothing in this path masks the payload before the first commit.

**1. Request path (POST `/api/v1/{organization}/signals/instances`)**
- `src/dispatch/signal/views.py:70`, `create_signal_instance`. It resolves the project, then the signal definition by `externalId`/`variant` from `raw`, falling back to the default definition. If none exists it returns 404.
- It calls `signal_service.create_instance` (`src/dispatch/signal/service.py:650`) and then `db_session.commit()`. `create_instance` stores `raw` as a JSON copy with no masking (`service.py:661-683`).
- The route returns the row without running the flow. A 409 is returned on an ID conflict.

**2. Processing (later, asynchronous)**
- The flow isn't called from the route. Instances are processed by `signals process` (`src/dispatch/cli.py:938`), which picks up unprocessed rows (`filter_action` and `case_id` both null, oldest first, 500 per pass) and calls `signal_instance_create_flow`. `process_signal_batch` (`src/dispatch/signal/flows.py:385`) does the same thing for the batch path.
- `signal_instance_create_flow` (`flows.py:46`) is where masking happens. Line 60 is `signal_instance.raw = redact_raw(signal_instance.raw)`, which runs before entity extraction, so entities are extracted from the masked payload.
- Then `filter_signal` (`flows.py:78`, `signal/service.py:866`) applies snooze and dedup. If it filters, the flow returns early. Canary instances and definitions with `create_case` off also return early. Otherwise a case is created (`flows.py:188`), followed by `case_flows.case_new_create_flow`.

**3. Masking function and defaults**
- `redact_raw` in `src/dispatch/signal/redaction.py:10`. It returns a copy, not in-place. Keys match case-insensitively at any depth, inside dicts and lists. Values that are not dicts or lists are not touched, so secrets inside strings are not masked. The replacement value is `[REDACTED]`.
- Default keys, from `src/dispatch/config.py:98-102` (overridable with the `SIGNAL_REDACTED_RAW_FIELDS` env var): `password, secret, api_key, session_token, authorization`.
- Matching is by exact key name. `apiKey`, `x-api-key`, and `token` are not matched.

**4. Is the unmasked payload written to the database?**
Yes, in two places.
- The POST commit (`views.py`, after `create_instance`) persists the full unmasked `raw`. That is the case from the moment the request returns until the processing loop runs. Processing can lag behind, so the window can be significant.
- The masked value only replaces it when `signal_instance_create_flow` commits. Note that the flow's commit comes only after entity extraction (when entity types exist), otherwise the first commit after redaction, such as the one in `process_signal_batch`. Either way the unmasked copy is overwritten, not deleted. Database backups, WAL, and audit logs made in that window keep it.
- `SignalInstanceRead` is the response model. I did not confirm whether it includes `raw`. If it does, the caller gets the unmasked payload back, but that is data the caller already sent.

**Not verified**
- I did not run the flow or check whether it's the only writer of the instance after creation. The Slack and AWS plugins also create instances (`plugins/dispatch_aws/plugin.py`), and I did not trace those.
- The `consume_signals` command (`cli.py:880`) may be another ingestion path. I did not trace it.
- I made no code changes.

----- next turn -----

The change responsible is `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02). It added `[:1]` to the JSONPath match in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`, around line 290). That slice keeps only the first match, so an entity type whose JSONPath matches several fields produced only one entity.

**Fix:** I removed the `[:1]` slice and the comment that came with it, restoring the line to `matches = jpath.find(signal_instance.raw)`. Nothing else changed, and I didn't touch any tests.

**Verification:** `python -m pytest tests/entity -q` passes, 11 of 11. Before the fix, `test_find_entities_with_field_only` failed with `assert 1 == 2`.

The change is uncommitted. The working tree still has the earlier restricted-case filter fix, the incident delete-route fix, and the new `tests/incident/` test.

----- next turn -----

The cause: the masking runs, but the entity JSONPath still matches the masked key and turns the `[REDACTED]` placeholder into an entity. Every instance with a masked token then gets the same `[REDACTED]` entity, and the deduplication filter groups them into one case.

**Fix** (`src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression`)
- Entities are now extracted from `redact_raw(signal_instance.raw)` instead of the raw payload. This covers every caller of `find_entities`, not only the signal flow. The `entity_type` create/update recalculation path never masked before, so it was exposed too.
- Any match whose value is `MASK` is skipped, so the placeholder can't become an entity.
- The masking itself is unchanged, and `signal_instance.raw` is not mutated (a test checks this).

**Tests** (new file `tests/entity/test_entity_redaction.py`, existing tests untouched)
- A JSONPath aimed at `session_token` produces no entities.
- An unmasked `user` field still produces its entity when a masked `session_token` type is alongside it.
- The raw payload is unchanged after extraction.

**Verification**
- `python -m pytest tests/entity tests/signal -q`: 46 passed, 1 skipped.
- With the entity service change stashed, the two tests that cover the bug fail, and they pass again after the change is restored.

**Not done**
- I didn't find which commit introduced the placeholder matching. I can trace it if you want it for the report.
- The change is uncommitted. The working tree also has the earlier restricted-case, incident-route, and entity-type changes.

----- next turn -----

**Investigation 1: unprotected mutating routes and the deleted check**

I listed the POST, PUT, PATCH, and DELETE routes in the case and incident views that had no `PermissionsDependency`. Five handlers qualified. Two case handlers, `create_case_channel` and `create_case_resources`, are open on purpose, as is `create_incident`. The fifth, `delete_custom_event`, was a regression. Commit `328359b5` changed its permission from `IncidentCommanderOrScribePermission` to `IncidentEventPermission`, and commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed the check entirely. I restored the check and added `tests/incident/test_incident_views_permissions.py`, which fails if the check goes missing again. The test passes with the fix and fails without it.

**Investigation 2: restricted cases visible to non-participants**

The cause was in `restricted_case_filter` (`src/dispatch/database/service.py`). Commit `42699ebc` ("refactor(database): flatten the restricted case filter") flattened the OR and dropped the `and_` that tied restricted visibility to participation. Every restricted case matched for non-admin users. The commit also undid the earlier security fix `b05613b5`. I restored the grouping. The tests in `tests/database/test_service.py` and `tests/case` pass (40 tests), and the existing test fails without the fix. I did not change any existing tests. I confirmed the filter is registered for `Case` and used by `search_filter_sort_paginate`, but I did not trace the cases list route end to end.

**Investigation 3: signal masking and the entity extraction bugs**

I traced `POST /api/v1/{organization}/signals/instances` (`src/dispatch/signal/views.py`). The route stores the raw payload unmasked and commits it. The payload is masked later, when the processing loop runs `signal_instance_create_flow`. This masking lives in `redact_raw` (`src/dispatch/signal/redaction.py`), and the default keys are set in `src/dispatch/config.py`. The masked value only overwrites the stored copy when that later step commits, so the unmasked payload is in the database for a while.

Two extraction bugs were found:
- **Only the first match:** commit `beb60cc4` added `[:1]` to the JSONPath match, so an entity type matching several fields produced only one entity. I reverted that line. `tests/entity` passes (11 tests).
- **Masked value became an entity:** an entity JSONPath pointing at a masked key matched the `[REDACTED]` placeholder, and that value became an entity. The deduplication filter then grouped unrelated instances. `find_entities` now extracts from a redacted copy and skips any match equal to the mask. I added `tests/entity/test_entity_redaction.py` with three tests. Two fail without the fix. The 46 tests in `tests/entity` and `tests/signal` pass with it.

**Open items**
- The `ObjectInUse` teardown error when a test imports `dispatch.main` is unexplained. I worked around it by importing the router directly.
- I did not check whether the create handlers enforce permissions inside the function body.
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