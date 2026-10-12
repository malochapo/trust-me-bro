Four state-changing routes have no `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
3. `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)

I also found `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (incident views, line 503). It declares no `dependencies=` argument, so it is a fifth match. My first grep missed it because the decorator spans several lines without a permissions line, and I confirmed it by reading the decorator block.

The routers are plain `APIRouter()` instances with no router-level dependencies, so these five routes have no permission check at the router level either. I only checked route definitions, as you asked. I did not check whether the handler bodies perform their own authorization.

No code was changed.

----- next turn -----

Yes, one of the five is a regression, and I've restored its check and added a test for it.

**The regression: `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`)**
- The check was removed in commit `28c21e1e` ("refactor(incident): tidy custom event routes"). That commit was labelled a refactor and deleted only the `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line.
- I restored that line in `src/dispatch/incident/views.py`, matching the other custom-event routes.

**Not regressions**
- `POST /case` and `POST /incident`: open on purpose, as you said.
- `POST /case/{case_id}/resources/conversation` and `POST /case/{case_id}/resources`: added without a check in `ced74f33` and `f08a22b3`. I found no commit that removed one, so these look like unguarded routes rather than regressions. You may still want to decide whether they should be guarded.

**The test**
- New file `tests/incident/test_views.py`. It looks up the route on the incident router and asserts that `IncidentEventPermission` is among its `PermissionsDependency` classes.
- It passes with the fix. With the fix stashed, it fails, so it will catch the check going missing again.
- `python -m pytest tests/incident tests/case` runs 16 tests, all passing.

I did not run the full test suite.

----- next turn -----

The cases list was showing restricted cases to people who are not participants. The cause is a dropped `and_` in the case visibility filter, and the regression came from commit `42699ebc`.

**The cause**
- `restricted_case_filter` in `src/dispatch/database/service.py` allowed a case through if `Case.visibility == restricted`, with no participant check. The participant match applied only to the `open` branch.
- The incident version of this filter has the check.
- `42699ebc` ("refactor(database): flatten the restricted case filter", Sep 2 2025) removed the `and_(...)` wrapper. The commit was labelled a refactor, but the change altered behaviour. Commit `b05613b5` (the authz hardening) had introduced the correct version.

**The fix**
- I restored the `and_(Case.visibility == restricted, IndividualContact.email == current_user.email)` branch, matching the incident filter.
- Admin, owner and manager roles still see all cases, as before.

**Verification**
- I did not change any tests.
- `tests/database/test_service.py`, `tests/case/test_case_service.py`, `tests/incident` and `tests/case` pass: 51 tests.
- Without the fix, `test_restricted_case_filter_with_test_data` fails (it sees 4 cases where it expects fewer), so the existing test already covers this bug.

The change is uncommitted, alongside the earlier changes to `incident/views.py` and the new `tests/incident/test_views.py`.

----- next turn -----



----- next turn -----

The masking happens in a background step, not in the POST handler. The POST handler stores the raw payload unmasked, so the unmasked payload is written to the database during the request.

**Request path**

1. **`POST /instances`** is `create_signal_instance` in `src/dispatch/signal/views.py:70`. It resolves the project and the signal definition by `externalId` or `variant`, falling back to the project's default signal. It then calls `signal_service.create_instance` (`src/dispatch/signal/service.py:650`) and commits. It does not call the processing flow, and it does not redact anything.
2. **`create_instance`** stores `raw` as JSONB in `signal_instance.raw` (`service.py:680`). The copy is only JSON round-tripped and `oncall_service` is removed. Nothing is masked.
3. **Background processing.** `main_processing_loop` (`src/dispatch/signal/flows.py:441`) runs `process_organization_signals`, which selects up to 500 instances with `filter_action IS NULL` and `case_id IS NULL` (`service.py:900`). Each one goes through `process_signal_batch` and then `signal_instance_create_flow` (`flows.py:46`).
4. **Masking.** `signal_instance_create_flow` runs `signal_instance.raw = redact_raw(signal_instance.raw)` at `flows.py:60`, before entity extraction. The comment says the masking is there so entities are not extracted from secrets.
5. **Filtering.** `filter_signal` (`service.py:866`) applies snooze, then deduplication, and commits. If it sets a filter action, the flow returns there. A canary instance also returns after that commit. Otherwise, if `signal.create_case` is false, the flow stops. Otherwise it creates a case with `visibility=open`, and the title and description come from the signal definition, not from `raw`.

**Where masking happens**

- Function: `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` in `src/dispatch/signal/redaction.py`. It walks dicts and lists recursively and replaces the value of any matching key with `"[REDACTED]"`.
- Default keys, from `src/dispatch/config.py:98`: `password`, `secret`, `api_key`, `session_token`, `authorization`. They are overridable with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable.
- Matching is case-insensitive and exact on the key name. It is not a substring match and it does not inspect values. So `apiKey`, `x-api-key` and `token` are not masked, and a secret inside a free-text string is not masked.
- The commit that added it is `d2675cf4` ("feat(signal): mask sensitive raw fields before processing"). No tests in `tests/` reference `redact`.

**Is the unmasked payload written to the database?**

Yes, in two places:

- **At POST time.** `create_instance` and the view's `db_session.commit()` (`views.py:119`) write the full unmasked `raw` to the `signal_instance.raw` column. This happens before any redaction. The row stays unmasked until processing reaches the first commit after line 60 in the flow. That commit is either the entity commit (only when entity types exist) or the one in `filter_signal`, which always runs. From then on the stored value is the masked one. The redacted object is the same ORM instance, so the flow's commit overwrites the column.
- **In the POST response.** `SignalInstanceRead` includes `raw`, and the response is built from the instance returned by `create_instance`, which still holds the unmasked payload. The caller receives its own secrets back. This is low severity because it is the caller's own data, but it is not masked.

Two things I inferred from reading the code rather than running it:

- If processing raises before `filter_signal` commits, `process_signal_batch` rolls back. The masking is lost, the row keeps the unmasked `raw`, and it stays unprocessed, so the loop retries it. Under that failure, the unmasked payload persists indefinitely.
- The window between POST and processing is up to one loop cycle (`LOOP_DELAY` is 60 seconds), plus batch time. During that window, `GET /instances` returns the unmasked payload.

I did not run the code or the tests. Nothing in the repository was changed.

----- next turn -----

The change responsible is `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, Sep 2 2025). It added `[:1]` to the JSONPath lookup in `find_entities` (`src/dispatch/entity/service.py`), so each entity type kept only its first match. Its commit message says it was a perf change, but slicing the result does not save any work, because `jpath.find` has already collected every match.

**The fix:** I removed the `[:1]` slice and the comment that went with it, so the line is back to `matches = jpath.find(signal_instance.raw)`. No tests were changed.

**Verification:** `python -m pytest tests/entity -q` gives 11 passed. Before the fix, `test_find_entities_with_field_only` failed with `assert 1 == 2`.

The working tree now has `src/dispatch/entity/service.py` modified, alongside the earlier changes to `database/service.py`, `incident/views.py` and the untracked `tests/incident/`. Nothing is committed.

----- next turn -----

The cause is that a masked value was being turned into an entity. Every instance of the signal got the same entity value, `[REDACTED]`, and the deduplication filter on that entity type then grouped them into one case. The fix is in `find_entities`, which all entity extraction goes through. The masking itself is unchanged.

**Why it happened**
- The signal flow masks `signal_instance.raw` at `flows.py:60`, then calls `find_entities`. That function's JSONPath search picked up the `"[REDACTED]"` string from the session-token key and created an entity from it.
- Because the value is the same on every instance, the deduplication filter matched all of them.
- The entity-type reprocessing path (`entity_type/service.py` and `entity_type/flows.py`) reads `raw` straight from the database. Instances that have not been through the flow yet still hold the unmasked token there, so that path could turn the real secret into an entity value. That was the second gap.

**The fix** (`src/dispatch/entity/service.py`)
- `find_entities` now runs the JSONPath search on `redact_raw(signal_instance.raw)`, so it works on a masked copy whichever path called it.
- Matches whose value is still `MASK` are skipped.
- `redact_raw` and the default key list are unchanged.

**The test** (new file `tests/entity/test_entity_redaction.py`, no existing tests changed)
- `test_find_entities_never_returns_masked_values` checks that a raw session token gives no entity, even before masking.
- `test_find_entities_ignores_placeholder_in_masked_payload` checks that a `[REDACTED]` placeholder gives no entity and that a normal field in the same payload still does.
- Without the fix, both fail. With it, both pass.

**Verification:** `python -m pytest tests/signal tests/entity_type tests/entity` gives 51 passed and 1 skipped. The skip was already there and I did not check its cause.

**Not verified:** I did not inspect the production "GitHub: Personal access token exposed" signal or its data. The cause above follows from the code and the new tests reproduce it, but the analysts' cases were not checked directly. Existing cases that were grouped this way will not be regrouped by this change. Their entities would need cleaning up separately.

**Something I noticed but did not change:** in `entity_type/flows.py`, `entity_types = signal_instance.signal.entity_types.append(entity_type)` assigns `None`, because `append` returns `None`. The `if entity_types:` branch after it never runs, so that flow does nothing. It is outside this fix, so I left it alone.

Nothing is committed. The working tree now also has `src/dispatch/entity/service.py` with the change and the new `tests/entity/test_entity_redaction.py`, alongside the earlier changes.

----- next turn -----

## Recap

**1. Unguarded write routes and the deleted permission check (incident and case APIs)**

- Five state-changing handlers had no `PermissionsDependency` at HEAD: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, since anyone may report a case or incident.
- `delete_custom_event` is a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes", Jul 14 2025) dropped its `IncidentEventPermission` check. I restored the check in `src/dispatch/incident/views.py`.
- I added `tests/incident/test_views.py`, which asserts that the DELETE route keeps `IncidentEventPermission`. It passes with the fix and fails without it.
- `create_case_channel` and `create_case_resources` have never been guarded (commits `ced74f33` and `f08a22b3`), so they are not regressions. Whether they need a check is still open.

**2. Cases list showing restricted cases to non-participants**

- `restricted_case_filter` in `src/dispatch/database/service.py` let any non-admin user see every restricted case. The participant check was applied only to the open branch.
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sep 2 2025) removed the `and_()` that required the participant match. The commit was labelled a refactor but changed behaviour.
- I restored the check to match the incident filter. The existing test `test_restricted_case_filter_with_test_data` fails without the fix and passes with it. 51 tests pass across the database, case, incident and case suites. No tests were changed.

**3. Signal instance flow: masking, leaks and entity extraction**

- Masking happens in `redact_raw` in `src/dispatch/signal/redaction.py`. The signal flow calls it before entity extraction. The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`, matched case-insensitively on exact key names at any depth. The masking was introduced in `d2675cf4`.
- The unmasked payload is written to the database. `POST /instances` commits the raw payload as sent, and the flow masks it later. The POST response also returns the unmasked payload. Until the processing loop runs, the unmasked payload is stored.
- Entity extraction read the raw payload, so the masked placeholder became an entity value. Every instance with that field got the same entity, and the deduplication filter grouped them into one case. I changed `find_entities` in `src/dispatch/entity/service.py` to search a masked copy and skip the placeholder value. Two new tests are in `tests/entity/test_entity_redaction.py`. They fail without the fix and pass with it. The signal, entity type and entity suites pass (51 passed, 1 skipped).
- Entity extraction also returned only the first JSONPath match, so the entity tests failed (CI red). That came from `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sep 2 2025). The change saved no work, so I removed the slice. The entity suite passes again.

**Open items**

- Nothing is committed. Changes are in `src/dispatch/database/service.py`, `src/dispatch/entity/service.py` and `src/dispatch/incident/views.py`, plus the untracked `tests/incident/` and `tests/entity/test_entity_redaction.py`.
- Decide whether the two case resource routes should get a permission check.
- Check how many existing cases were grouped by the placeholder entity. This change does not fix them.
- `src/dispatch/entity_type/flows.py` assigns `None` from `append`, so that flow does nothing. Not fixed.

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