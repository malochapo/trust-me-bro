Five write routes have no `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
3. `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

The routers have no router-level dependencies, so these are the only write routes without a declared check. I didn't look at whether the function bodies enforce permissions by other means. I also didn't change any code.

----- next turn -----

The regression was `delete_custom_event` (`DELETE /{incident_id}/event/{event_uuid}`). Commit `28c21e1e` ("refactor(incident): tidy custom event routes") deleted its `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line and nothing else. The other four routes from my list were never protected, so they aren't regressions.

**Restored:** `src/dispatch/incident/views.py` now has the `IncidentEventPermission` dependency on `delete_custom_event`, the same as the other custom-event routes in that file.

**New test:** `tests/incident/test_incident_views_permissions.py` checks that the DELETE route declares `IncidentEventPermission`. I confirmed it fails with the check removed and passes with it restored. The incident, case, and api tests pass (16 passed), run with `python -m pytest`. I didn't run the full suite.

**Not changed, but worth a look:**
- `create_case_channel` (`POST /{case_id}/resources/conversation`) and `create_case_resources` (`POST /{case_id}/resources`) have never had a permission check. Both were added without one, in `ced74f33` and `f08a22b3`. Unlike `create_case` and `create_incident`, I don't see a reason for them to be open to anyone, so they look like a gap rather than a design choice. I left them alone since you asked only about regressions. I can add `CaseEditPermission` to them if you want.

Nothing is committed.

----- next turn -----

The cases list showed restricted cases to members who weren't participants. The cause was in `restricted_case_filter` (`src/dispatch/database/service.py`). Its `or_` included `Case.visibility == Visibility.restricted` on its own, so any restricted case passed the filter. The participant check was lost in an `and_` that got flattened away.

**Commit that introduced it:** `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). It turned `and_(restricted, participant-email match)` into two separate `or_` branches. The original check came from `b05613b5` (the sec(authz) commit), which is where the case filter first got its participant check.

**Fix:** I restored the `and_` so restricted cases are shown only when the current user is a participant. Admin, owner, and manager roles still see everything, as before.

**Verification:**
- `tests/database/test_service.py` and `tests/case` pass (40 passed) with the fix.
- With the fix stashed, `test_restricted_case_filter_with_test_data` fails, so the existing test does catch this bug. I didn't change any tests.

**Current working tree:** This fix is in `src/dispatch/database/service.py`, alongside the earlier `delete_custom_event` fix in `src/dispatch/incident/views.py` and the new `tests/incident/` test. Nothing is committed.

----- next turn -----



----- next turn -----

**Short answer:** Masking happens in `redact_raw()` in `src/dispatch/signal/redaction.py`, not on the POST request. It runs later, in the background signal processing flow. The default keys are `password`, `secret`, `api_key`, `session_token`, and `authorization`. Yes, the unmasked payload is written to the database, and it stays there until the processing flow overwrites it. The POST response also returns it unmasked.

**Trace**

1. **POST `/api/v1/{organization}/signals/instances`** (`src/dispatch/signal/views.py:70-127`, rate-limited to 1000/min)
   - Resolves the project, then the signal definition by `externalId`/`variant`, falling back to the default.
   - Calls `signal_service.create_instance()` (`src/dispatch/signal/service.py:643`). This stores `raw` as a JSON round-trip of the input, with no redaction (lines 661-681).
   - The view commits (`views.py:~118`) and returns the instance. `SignalInstanceRead` includes `raw`, so the caller gets the unmasked payload back.
   - No case is opened here. The instance is saved with `filter_action = None` and `case_id = None`.

2. **Background processing**
   - The `process_signals` CLI loop (`src/dispatch/cli.py:938`) and `process_organization_signals` (`src/dispatch/signal/flows.py:~440-470`) pick up unprocessed instances (`get_unprocessed_signal_instance_ids`, `service.py:~900`, up to 500 at a time).
   - Each instance is passed to `signal_instance_create_flow` (`src/dispatch/signal/flows.py:46`) inside `process_signal_batch` (`flows.py:385`), which commits on success and rolls back on exception.

3. **`signal_instance_create_flow`**
   - **Line 60:** `signal_instance.raw = redact_raw(signal_instance.raw)`. This is the masking step.
   - Entity extraction runs on the redacted payload, so secret values don't produce entities.
   - Commits if entities were found (`flows.py:~75`).
   - `signal_service.filter_signal()` (`service.py:866`) applies snooze and dedup, then always commits (`service.py:896`). If the instance is filtered, the flow returns here with no case.
   - Canary instances and signals with `create_case = False` also return here.
   - Otherwise it creates a case with `visibility=open` via `case_service.create`, sets `signal_instance.case`, and commits (`flows.py:~191`).

**Details you asked about**

- **Function:** `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` calls the recursive helper `_redact`. Matching is case-insensitive and exact, at any depth, inside dicts and lists. Matched values become `"[REDACTED]"`. Other values are returned unchanged.
- **Default keys:** set in `src/dispatch/config.py:98-102` as `password,secret,api_key,session_token,authorization`. It can be overridden with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable.
- **Gaps from exact matching:** keys like `apiKey`, `x-api-key`, `client_secret`, or `access_token` are not masked.

**Is the unmasked payload written to the database?** Yes, in two ways:

- **Immediately:** the POST commit saves the raw payload unmasked. It remains in the `raw` JSONB column until the processing flow runs.
- **If processing fails:** `process_signal_batch` rolls back on exception, which discards the in-memory redaction. The instance keeps its unmasked `raw`, is not marked processed, and gets retried. If the failure is persistent, the payload stays unmasked indefinitely.
- **After success:** the redacted payload overwrites `raw`. The original value is not kept as a copy. It may still exist in Postgres WAL or backups.

**Other notes**

- `tests/` has no tests that reference `redact_raw` or the redaction config.
- `signal_service.update_instance` (`service.py:~730-739`) also writes `raw` without redaction. I didn't check its callers, so I can't say whether it's on a reachable path.
- I did not run anything or change any code.

----- next turn -----

The entity extraction bug is fixed. `tests/entity` now passes, 11 of 11, up from 10 of 11.

**Cause:** commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, Sep 2 2025) changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`. That keeps only the first match for each JSONPath, so a path matching several fields produced only one entity. The failing test was `test_find_entities_with_field_only`, which failed with `assert 1 == 2`.

**Fix:** I removed the `[:1]` slice and its comment, so the code is back to `matches = jpath.find(signal_instance.raw)`. That is the only change to the file, and I didn't touch any tests.

**Not done:** I didn't run the full test suite, and I didn't commit anything. The working tree still has the earlier uncommitted changes: the `delete_custom_event` guard, the new `tests/incident/` test, and the restricted-case fix in `service.py`.

----- next turn -----

Masked values no longer become entities. The new test fails without the guard and passes with it, and `tests/entity` passes (13 of 13). I did not run the full suite.

**Why instances were grouped:** the flow masks the payload before it extracts entities (`signal/flows.py:60`, then `find_entities`). So for a JSONPath aimed at a masked key, the match is the placeholder `"[REDACTED]"`. Every such instance gets an entity with that same value, and the entity-based dedup filter groups them into one case. The masking itself is unchanged.

**Fix:** in `find_entities` (`src/dispatch/entity/service.py`), a string match equal to `MASK` is skipped. That function is the only JSONPath extraction path, and the entity-type re-extraction paths (`entity_type/service.py:95`, `entity_type/flows.py:29`) also call it, so the guard covers all of them. The guard checks the value rather than the key path, because `redact_raw` replaces every masked value with the string `MASK`.

**Test:** `tests/entity/test_entity_masking.py` has two tests. The first redacts a payload with a `session_token` and checks that no entity is created. The second is a control: an unmasked token still produces an entity.

**This session's changes:**
- The `[:1]` removal from the previous fix is still in place.
- The new guard is in `src/dispatch/entity/service.py`.

**Not covered:** a few things are outside this fix:
- Unprocessed instances keep their raw, unmasked payload until the flow runs (the issue I reported earlier). If an entity type is re-extracted from one of those, the real token becomes an entity value. The guard only catches the placeholder, so that case is still open. Fixing it would mean changing the masking timing, which you asked me to keep.
- The redaction config only matches exact key names, so masked-looking keys such as `apiKey` are not masked and their values can still become entities.

----- next turn -----

Recap of today's three investigations. Nothing is committed yet. The changes are uncommitted in the working tree.

**1. Unguarded write routes (case and incident APIs)**
Five write routes had no `PermissionsDependency` at HEAD. Three are case routes: `create_case`, `create_case_channel`, and `create_case_resources`. Two are incident routes: `create_incident` and `delete_custom_event`. Creating a case or incident is meant to be open to anyone, so those are design choices. `delete_custom_event` was a regression. Its `IncidentEventPermission` check was removed in `28c21e1e` (Sam Ortega, 2025-07-14, "refactor(incident): tidy custom event routes"). I restored the check in `src/dispatch/incident/views.py`. I also added `tests/incident/test_incident_views_permissions.py`, which fails if the check goes missing again. I confirmed the test fails with the line removed.
Still open: `create_case_channel` and `create_case_resources` have never had a permission check (added in `ced74f33` and `f08a22b3`). I did not change them. Adding `CaseEditPermission` is a one-line change each if you want it.

**2. Restricted cases visible to non-participants**
`restricted_case_filter` in `src/dispatch/database/service.py` had lost its participant check. Its `or_` included `Case.visibility == Visibility.restricted` as a bare term, so every restricted case passed. The check was flattened in `42699ebc` (Sam Ortega, 2025-09-02, "refactor(database): flatten the restricted case filter"). I restored the `and_` so restricted cases show only to their participants. Admin, owner, and manager roles are unchanged. `tests/database/test_service.py` and `tests/case` pass (40 passed). The existing restricted-case test fails without the fix. I did not change any tests.

**3. Entity extraction and masked values**
- **Extraction bug:** `beb60cc4` (Sam Ortega, 2025-09-02, "perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath matches. That kept only one entity per entity type. I removed the slice. `tests/entity` failed with `1 == 2` before and passes now.
- **Grouping bug:** the signal flow masks the payload before entity extraction. A JSONPath aimed at a masked key therefore matched the `"[REDACTED]"` placeholder, and every such instance got the same entity. The dedup filter then grouped them. I added a guard in `find_entities` (`src/dispatch/entity/service.py`) that skips any match equal to `MASK`. That covers all callers, since they all go through `find_entities`. I added `tests/entity/test_entity_masking.py`, which includes an unmasked control case. The new test fails without the guard. `tests/entity` passes (13 passed).
- **Masking:** `redact_raw` in `src/dispatch/signal/redaction.py` masks values for keys that match case-insensitively at any depth. The masking is unchanged.
- **Open issue:** unprocessed instances keep the unmasked payload in the database until the flow runs. Re-extracting entities from one of them can still turn the real token into an entity value. The guard only covers the placeholder.

I did not run the full test suite.

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