Five mutating routes have no `PermissionsDependency` in their decorator:

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""`, `create_case`, line 162
2. `POST /{case_id}/resources/conversation`, `create_case_channel`, line 236
3. `POST /{case_id}/resources`, `create_case_resources`, line 260

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""`, `create_incident`, line 117
5. `DELETE /{incident_id}/event/{event_uuid}`, `delete_custom_event`, line 503

I checked each mutating decorator in both files, and the case router has no router-level dependencies (`APIRouter()` is bare). I didn't change any code.

----- next turn -----

One of the three was a regression: `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`). I restored its check and added a test. I haven't committed.

**The regression**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes", Sam Ortega, Jul 14 2025) removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from the route. The commit message doesn't mention permissions, so it reads as an accidental removal.
- The fix puts that line back in `src/dispatch/incident/views.py:506`.

**Not regressions**
- `POST /case/{case_id}/resources/conversation` (`create_case_channel`) was added in `ced74f33` without a permission check.
- `POST /case/{case_id}/resources` (`create_case_resources`) has never had one, since `f08a22b3`.
- I left both alone. They may be oversights, but the history doesn't show a check that was removed. Someone should decide whether they need one.

**The test**
- New file: `tests/incident/test_incident_event_permissions.py`. It finds the DELETE route for `/{incident_id}/event/{event_uuid}` on the incident router and asserts that `IncidentEventPermission` is among its `PermissionsDependency` classes.
- I ran it with the fix stashed: it failed. With the fix restored: it passed.
- `python -m pytest tests/incident tests/case` gives 16 passed.

One more thing from the first list: `POST /incident/{incident_id}/...` at `views.py:163` is guarded only by `IncidentViewPermission`. That's a weaker check than the edit permission used by most other writes. It's not part of the "no check" list, so I haven't touched it, but it may be worth a look.

----- next turn -----

The cases list was showing restricted cases to people who aren't participants. The fix is in place and the database and case tests pass (40 passed).

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` had its visibility rule flattened into a plain `or_`. The restricted clause no longer required the user to be a participant, so every restricted case matched for non-admin roles. The incident version of the same filter still has the participant check.

**Commit:** `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, Sep 2 2025). It was labelled a refactor, but it changed behavior: it removed the `and_` that tied restricted visibility to participation. The earlier security fix `b05613b5` (#6155) had introduced the filter, with the check in place.

**Fix:** I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` clause, so the case filter matches the incident filter again.

**Tests:** I did not change any tests. `test_restricted_case_filter_with_test_data` was failing before the fix (it got 4 cases where it expected 3) and passes now.

I did not run the HTTP list endpoint itself. I'm relying on the fact that the case list goes through `search_filter_sort_paginate` with this filter, which is how `b05613b5` wired it in.

Uncommitted changes in the working tree now also include the earlier `delete_custom_event` fix and its new test.

----- next turn -----



----- next turn -----

The raw payload is first written to the database unmasked. Masking happens later, in a background pass, and the mask does not cover every sensitive key name.

**Path from the POST to a case or a filter**

1. **Route** (`src/dispatch/signal/views.py:70-129`, `create_signal_instance`). It resolves the project, then the signal definition by `externalId`/`variant`, falling back to the default definition. It calls `signal_service.create_instance` and then `db_session.commit()`. The route returns the instance without running any processing.
2. **Instance creation** (`src/dispatch/signal/service.py:650-697`, `create_instance`). It copies `raw`, drops `oncall_service`, round-trips it through JSON, and adds the row to the session. There is no masking here.
3. **Background processing.** The route does not call the flow. A separate loop picks up instances with `filter_action IS NULL` and `case_id IS NULL` (`service.py:900-913`), oldest first. `process_organization_signals` (`src/dispatch/signal/flows.py:406`) runs them through `process_signal_batch` (`flows.py:385`). The loop runs under `main_processing_loop` (`flows.py:~460`, started by `cli.py:938` `process_signals`). `cli.py:1004` does the same thing in another consumer path.
4. **Flow** (`src/dispatch/signal/flows.py:46`, `signal_instance_create_flow`). The first real step is `signal_instance.raw = redact_raw(signal_instance.raw)` (`flows.py:60`). Entity extraction, filtering, canary handling, and case creation all run after this, so they see the masked payload.
5. **Filter** (`service.py:866`, `filter_signal`). Dedup, snooze, and other filter actions set `filter_action` and `case_id`. An instance that is filtered returns early and is never re-queued. Otherwise a case is created when `signal.create_case` is set. Canary instances are stored and returned.

**Masking function**

- `redact_raw` in `src/dispatch/signal/redaction.py:10-17`. It returns a copy, not an in-place edit. Keys match case-insensitively at any depth, including inside lists. Non-dict and non-list values pass through unchanged. The mask string is `"[REDACTED]"`.
- Default keys come from `src/dispatch/config.py:98-102`, read from the `SIGNAL_REDACTED_RAW_FIELDS` env var: `password, secret, api_key, session_token, authorization`.
- It is the only caller of `redact_raw`, and it is only called from `flows.py:60`.

**Is the unmasked payload written to the database?**

Yes. `create_instance` stores the raw payload unchanged, and the route commits it (`views.py`, the `db_session.commit()` right after `create_instance`). That is the first write, and it happens before any masking. Redaction only changes the in-memory object. It is persisted later, when a commit runs in `process_signal_batch` or in the entity-extraction commit. If the flow fails, `process_signal_batch` rolls back, and the unmasked payload stays in the database.

**Other things I noticed**

- The masking is exact key-name matching, not substring matching. `apiKey`, `x-api-key`, `access_token` and `client_secret` are not masked by default.
- `service.create_signal_instance` (`service.py:162`) and the AWS plugin path (`plugins/dispatch_aws/plugin.py:113`) call `create_instance` and never reach the flow, so their payloads are never masked unless they are processed later.
- `update_instance` (`service.py:726-739`) writes `raw` straight to the database with no masking. I did not check its callers.

I read the code only and did not run anything or change any files. The line numbers are from the current working tree, which has uncommitted changes in `service.py` and `incident/views.py`.

----- next turn -----

The cause was commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, Sep 2 2025). It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`, so each JSONPath entity type produced at most one entity. A JSONPath that matches several fields lost every match after the first.

I reverted that line to `matches = jpath.find(signal_instance.raw)`. The change is a one-line revert and no tests were touched.

Results:
- `tests/entity`: 11 passed. Before the fix, `test_find_entities_with_field_only` failed with `assert 1 == 2`.
- `tests/signal` and `tests/entity` together: 43 passed, 1 skipped.

The "perf" motivation is worth a look. If the slice was meant to save work, it cut correctness for every multi-match path. A real speedup would need a different approach, such as stopping early only when the entity type is one-match-only, and I did not attempt that.

Nothing is committed. The working tree also still has the earlier uncommitted changes in `database/service.py`, `incident/views.py` and `tests/incident/`.

----- next turn -----

Masked values no longer become entities, and the new test catches the bug.

**Why it happened:** `signal_instance_create_flow` masks `raw` in memory (`flows.py:60`) and then calls `find_entities`. For the "GitHub: Personal access token exposed" signal, the entity type's JSONPath points at the session token, so it reads the mask string `"[REDACTED]"`. Every instance then gets an entity with the same value, and the deduplication filter on that entity groups them into one case.

**Fix:** In `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`), a match is now skipped when its value equals `MASK`. This is the only place entities are extracted from a payload, so the guard covers all of them. I did not change the masking itself.

**Test:** I added `tests/entity/test_entity_redaction.py` with two tests:
- A masked JSONPath target produces no entity.
- An unmasked value in the same payload still becomes an entity.

Both pass with the fix. With the guard removed, the first fails with `[<Entity #1>] == []` and the second with `'[REDACTED]'` in the results. `tests/entity` and `tests/signal` pass together: 45 passed, 1 skipped.

**Things to be aware of:**
- A payload that contains the literal text `[REDACTED]` will also be skipped. I think that's acceptable, but say if you want it narrower.
- Entities already created from masked values stay in the database, and the cases they grouped are unaffected. Those `[REDACTED]` entities should be found and deleted, and the affected cases checked. I have not done that, since it changes data.
- The earlier `[:1]` revert is part of this diff too, so the entity file now differs from HEAD only by the revert and this guard.

Nothing is committed.

----- next turn -----

Both investigations are done and nothing is committed. The changes sit in the working tree.

**1. Permission regression on custom event deletion**
- Four handlers in `case/views.py` and `incident/views.py` change data without a permission check. Two of them are `create_case_channel` and `create_case_resources` in `case/views.py`. They never had a check, so they are a design gap, not a regression, and I left them alone. The other is `incident.delete_custom_event`.
- `incident.delete_custom_event` lost its `IncidentEventPermission` check in `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored it. A new test, `tests/incident/test_incident_event_permissions.py`, fails without the check and passes with it.
- `POST /{incident_id}/...` at `incident/views.py:163` is guarded only by `IncidentViewPermission`, so a write goes through a view-level check. I reported it and did not change it.

**2. Members seeing restricted cases they are not part of**
- Cause: `restricted_case_filter` in `database/service.py` lost its participant check. Restricted cases matched for every non-admin user.
- Introduced by `42699ebc` ("refactor(database): flatten the restricted case filter"), which was labelled a refactor but changed behavior. The filter itself came from `b05613b5`.
- Fix: restored the participant `and_` clause, matching `restricted_incident_filter`. `tests/database/test_service.py` and `tests/case` pass (40 passed). I did not run the HTTP list endpoint.

**3. Entity extraction keeping only the first match**
- Commit `beb60cc4` added `[:1]` to the JSONPath match list, so only the first match became an entity. I reverted that line. `tests/entity` passes (11 passed).

**4. Masked values becoming entities**
- Cause: the flow masks `raw` in memory before entity extraction. A JSONPath that points at a masked key reads `"[REDACTED]"`, so every instance got the same entity. The deduplication filter then grouped them.
- Fix: `_find_entities_by_jsonpath_expression` in `entity/service.py` skips values equal to `MASK`. The masking is unchanged. The new test file `tests/entity/test_entity_redaction.py` has two tests, and both fail without the guard. `tests/entity` and `tests/signal` pass together: 45 passed, 1 skipped.
- Still to do: entities already created from masked values remain in the database, and the cases they grouped need checking. I have not touched that data.

**5. Signal payload masking**
- The POST route stores the raw payload and commits it before any masking. Masking happens later in the processing flow. So the unmasked payload is written to the database.
- Masking applies at any depth and matches key names exactly, so `apiKey` and `access_token` are not masked by default.

UNPROTECTED_AT_START: case.create_case_channel, case.create_case_resources, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4