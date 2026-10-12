Six endpoints change data without a `PermissionsDependency` on their route. Five are in the case API and the incident API each has one.

**Case API (`src/dispatch/case/views.py`)**
- `case/views.py:162`: `POST /api/v1/cases` (`create_case`)
- `case/views.py:236`: `POST /{case_id}/resources/conversation` (`create_case_channel`)
- `case/views.py:260`: `POST /{case_id}/resources` (`create_case_resources`)

**Incident API (`src/dispatch/incident/views.py`)**
- `incident/views.py:117`: `POST` on the collection (`create_incident`)
- `incident/views.py:503`: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`)

The incident `DELETE` route at line 503 is the one with no `dependencies=` argument at all. The other five list a permission in their decorator or, for the case routes, have none.

I checked only the route decorators in these two files. I did not check permissions applied at `include_router` time, router-level dependencies, or middleware, so a route could be protected elsewhere. I made no code changes.

----- next turn -----

The one regression is the incident custom-event delete route. I restored its check, added a test that fails without it, and the change is uncommitted in the working tree.

**What I found**
- `DELETE /{incident_id}/event/{event_uuid}` (`src/dispatch/incident/views.py`) lost its `IncidentEventPermission` check in commit `28c21e1e` ("refactor(incident): tidy custom event routes"). That commit deleted one `dependencies=` line and nothing else. The POST and PATCH event routes on the same path still have the check.
- The two case routes, `POST /{case_id}/resources/conversation` and `POST /{case_id}/resources`, were added without a check in `ced74f33` and `f08a22b3`. Nothing ever removed one, so they aren't regressions. I left them alone. Whether they should be protected is your call.
- `POST` on the incident collection is the intentional open route, so I didn't touch it.

**Changes**
- `src/dispatch/incident/views.py`: added `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` to the DELETE route.
- `tests/incident/test_incident_views_permissions.py` (new): parametrized over the three custom-event routes (POST, PATCH, DELETE). It asserts each route's dependency list includes `IncidentEventPermission`. It reads route metadata and doesn't hit the database. I checked that it fails when the DELETE check is removed, and passes with the check restored.

**Test results**
- `python -m pytest tests/incident`: 3 passed.
- Full `python -m pytest`: 362 passed, 4 skipped, 8 failed. The failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py` (1) and `tests/entity/test_entity_service.py` (1). They also fail with my change stashed, so they predate this work and I did not investigate them.

I haven't committed anything.

----- next turn -----

The cases list shows restricted cases to people who aren't participants. The bug is in `restricted_case_filter` (`src/dispatch/database/service.py`), and commit `42699ebc` introduced it.

**Cause**
- Commit `42699ebc` (Sam Ortega, 2025-09-02, "refactor(database): flatten the restricted case filter") removed the `and_(...)` around the restricted-case condition.
- The filter became `open OR restricted OR participant-email-matches`. Any member could therefore see every restricted case in the project, not only the ones they participate in.
- The incident filter (`restricted_incident_filter`) was not affected.

**Fix**
- I restored the `and_` so the filter is `open OR (restricted AND participant email matches)`, matching the incident version. The change is in `src/dispatch/database/service.py`.

**Verification**
- `tests/database/test_service.py`: 25 passed, including `test_restricted_case_filter_with_test_data`, which failed before the fix with 4 results instead of 3.
- Full `python -m pytest`: 363 passed, 4 skipped, 7 failed. The 7 failures are the AI and entity tests that also failed before any of my changes, so they are not caused by this fix. I did not investigate them.
- I did not change any existing tests and did not add a new one, since the existing test covers this case.

Nothing is committed. The working tree has this fix, the earlier `incident/views.py` fix, and the new `tests/incident/` test file.

----- next turn -----



----- next turn -----

The unmasked payload is written to the database. The API commits it before any masking runs, and masking only happens later in a background loop. I read the code but did not run the API, so the sequence below is from reading, not observation.

## Path of a `POST /api/v1/{organization}/signals/instances`

**1. The request handler** (`src/dispatch/signal/views.py:70-129`, `create_signal_instance`)
- Resolves the project, then the signal definition by `externalId`/`variant` from the raw payload, falling back to the default. It returns 404 if none exists.
- Calls `signal_service.create_instance` (`src/dispatch/signal/service.py:650`). That builds a `SignalInstance` with `raw=json.loads(json.dumps(raw))`, a copy with no masking.
- Calls `db_session.commit()` at `views.py:120`. **The raw payload is committed here, unmasked.**
- Returns the instance. `SignalInstanceBase` declares `raw` (`models.py:394`), so the response most likely includes it unmasked too. I did not verify the response schema.

**2. The background loop picks it up** (the view does not call the flow)
- `main_processing_loop` (`src/dispatch/signal/flows.py:441`) → `process_organization_signals` (`flows.py:406`) → `get_unprocessed_signal_instance_ids` (`service.py:900`), which selects rows with `filter_action IS NULL` and `case_id IS NULL`, oldest first, up to 500.
- Each ID goes to `process_signal_batch` (`flows.py:385`), which calls `signal_instance_create_flow` (`flows.py:46`) and commits after each one. On exception it rolls back (`flows.py:403`).

**3. `signal_instance_create_flow`**
- `flows.py:60`: `signal_instance.raw = redact_raw(signal_instance.raw)`. This is the masking step.
- `flows.py:63-75`: entity extraction runs on the masked payload. Commit at `flows.py:75` if any entities were found.
- `flows.py:78`: `filter_signal` (`service.py:866`) applies snooze, then deduplication, then sets `filter_action` to `none` when nothing matched. It commits at `service.py:896`. A non-`none` action means the instance is **filtered out**; the flow returns at `flows.py:100`.
- `flows.py:103`: canary instances return without a case.
- `flows.py:106`: if the signal has `create_case` off, the flow returns.
- Otherwise it builds `CaseCreate` (`flows.py:173-187`, visibility `open`, title and description from the signal definition, not the payload), creates the case, and commits (`flows.py:191`). Then it runs `case_new_create_flow` (`flows.py:203`), identity engagement (`flows.py:212`), and workflows (`flows.py:219`).

## Masking function and defaults

- **Function:** `redact_raw` in `src/dispatch/signal/redaction.py:10`, with the recursive helper `_redact` at line 20.
- **Behaviour:** replaces the value of any dict key whose name matches, case-insensitively, at any depth inside dicts and lists, with `"[REDACTED]"`. Other values pass through unchanged. It returns a new structure and does not mutate the input.
- **Default keys:** `password`, `secret`, `api_key`, `session_token`, `authorization` (`src/dispatch/config.py:98-102`). They can be overridden with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable.
- **Limits:** matching is on exact key names, not substrings, so `db_password` or `token` is not masked by default. Secrets inside string values (for example a URL with credentials) are not masked.

## Is the unmasked payload written to the database?

Yes, in two places:

1. **At request time, `views.py:120`.** The raw payload is committed as received. It stays unmasked in `signal_instance.raw` (`models.py:239`) until the background loop processes the row. That wait can be up to the loop delay (60 s), longer with a backlog. The window is also longer if processing fails, because the masked update is rolled back (`flows.py:403`) and the unmasked value remains.
2. **After processing, the masked version overwrites it.** The masked payload is committed at `flows.py:75`, `flows.py:191`, or `service.py:896`. This happens for both filtered and created-case instances, so the stored value is the masked one once processing succeeds.

I did not check whether the database keeps history, such as WAL, backups, or audit tables, which could retain the unmasked value.

## Other observations

- Masking runs before entity extraction, so JSONPath-based entities cannot match a masked key.
- The other paths that create instances (the scheduler at `flows.py:231` and the AWS plugin at `plugins/dispatch_aws/plugin.py:57`) call `service.create_instance` too. They are not traced in full here, but they also rely on the background loop for masking.

No code was changed. If you want the unmasked value never stored, the likely fix is to apply `redact_raw` inside `service.create_instance` before the commit at `views.py:120`. The trade-off is that the flow would then see the masked payload from the start, which is already the case for entity extraction.

----- next turn -----

The entity regression is fixed. The change responsible is `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, committed 2025-09-02). It added `[:1]` to the `jpath.find(...)` call in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`). That capped every JSONPath at one match, so `asset[*].id` produced one entity instead of two.

**Fix:** I restored `matches = jpath.find(signal_instance.raw)` and removed the slice and its comment. No tests were changed.

**Verification:**
- `python -m pytest -q tests/entity`: 11 passed. `test_find_entities_with_field_only` failed before with `assert 1 == 2` and now passes.
- Full `python -m pytest -q`: 364 passed, 4 skipped, 6 failed. All 6 failures are in `tests/ai/test_ai_service.py`. They fail because the environment cannot reach `openaipublic.blob.core.windows.net` to download the tiktoken encoding. They are unrelated to this change, and I did not investigate them further.

**Trade-off:** `beb60cc4` was labelled a performance change. `jpath.find` still collects all matches before the loop, so the slice saved only the per-match loop work, not the JSONPath evaluation. If the performance goal still matters, it would need a different approach, and the tests show the intended behaviour is to return all matches.

Nothing is committed. The working tree now also includes the restricted-case filter fix and the incident custom-event route fix from earlier, plus the new `tests/incident/` file.

----- next turn -----

Masked values no longer become entities, so unrelated "GitHub: Personal access token exposed" instances stop being grouped together.

**Why it happened**
- The flow masks `signal_instance.raw` before extraction (`src/dispatch/signal/flows.py:60`), but the JSONPath extractor in `src/dispatch/entity/service.py` read whatever raw it was given.
- A JSONPath pointing at `session_token` still matched the masked key. The match's value was the literal string `"[REDACTED]"`, so every instance produced the same entity. The deduplication filter on that entity type then grouped them.
- Other callers, such as the entity-type create and recalculation flows (`entity_type/service.py:95`, `entity_type/flows.py:29`), load instances from the database. An instance that has not been processed yet still holds the unmasked payload there, so those paths could extract real secrets.

**Fix** (`src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression`)
- The extractor now applies `redact_raw` to the payload itself, so every caller gets masked data.
- It skips any match whose value equals `MASK`.
- The masking rules are unchanged.

**Test**
- New file `tests/entity/test_entity_masked_values.py`, with two tests:
  - a `*` JSONPath yields only the unmasked field (`alice`), not the masked token;
  - a JSONPath aimed directly at the masked key yields no entities.
- Both fail with the fix stashed and pass with it applied. No existing tests were changed.

**Results**
- `tests/entity`: 13 passed.
- Full suite: 366 passed, 4 skipped, 6 failed. The 6 failures are the same AI-service tests that need network access for the tiktoken download, unrelated to this change.

**Not verified or out of scope**
- `find_entities` no longer applies regular expressions. Only JSONPath matching happens in the code I read, although `entity_type_pairs` still carries the regex. I did not change that.
- The unprocessed-instance window and the unmasked write at `views.py:120` from my earlier trace still exist. This fix only covers entity extraction.

Nothing is committed. The working tree now has the restricted-case fix, the incident route fix, the entity fixes, and the new test files.

----- next turn -----

Both investigations are done. Nothing is committed; the changes are in the working tree.

## Recap

**1. Write routes without a permission check (case and incident APIs)**
- Before my changes, five data-changing handlers had no `PermissionsDependency`: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident`, and `incident.delete_custom_event`.
- `create_case` and `create_incident` are open by design: anyone may report a case or an incident.
- `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its check. I restored it in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_views_permissions.py`, which fails if the check is removed again.
- The two case resource routes (`case.create_case_channel`, `case.create_case_resources`) were added without checks in `ced74f33` and `f08a22b3`, so they are not regressions. Whether they should have a check is an open decision. I did not change them.

**2. Restricted cases shown to members (cases list)**
- `restricted_case_filter` in `src/dispatch/database/service.py` was flattened to `open OR restricted OR participant-email-matches`, so members saw every restricted case. The fix restores `open OR (restricted AND participant-email-matches)`, matching the incident filter.
- The existing tests were not changed. `tests/database/test_service.py` passes.

**3. Entity extraction keeping only the first match**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added a `[:1]` slice. I removed it in `src/dispatch/entity/service.py`. `tests/entity` passes (11 tests at that point).

**4. Masked values becoming entities (grouping of unrelated GitHub token instances)**
- Masking runs before extraction in the create flow, but the extractor read the raw payload as given. A JSONPath on a masked key matched the literal `"[REDACTED]"`. Every such instance produced the same entity, and the deduplication filter grouped them.
- Recalculation and entity-type creation load instances from the database, where the unmasked payload can still be stored, so they bypassed masking entirely.
- Fix: the extractor now applies `redact_raw` itself and skips any match equal to `MASK`. The masking rules are unchanged.
- Test: `tests/entity/test_entity_masked_values.py`, two tests. Both fail without the fix and pass with it.

**Results**
- Full suite: 366 passed, 4 skipped, 6 failed. The 6 failures are in `tests/ai/test_ai_service.py`; they need network access to download the tiktoken encoding, so they are unrelated to these changes.

**Open items**
- The two case resource routes need a decision on permission checks.
- The raw payload is committed unmasked at `src/dispatch/signal/views.py:120` before background processing masks it. Masking happens later, but until then the unmasked value is in the database. The entity fix does not address this.
- `find_entities` no longer applies regular expressions, although the type pairs still carry them. I did not investigate this.
- Pickaxe search returned a different commit for the restricted filter (`b05613b5`, an authz change); `42699ebc` is the commit that removed the `and_` (confirmed with `git blame` and `git show`).

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