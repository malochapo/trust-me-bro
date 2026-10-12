Four data-changing routes declare no `PermissionsDependency` in their route definition. I read the route decorators in both files and changed no code.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
3. `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

The incident delete is the odd one out. Every other incident event route (create, update, export) uses `IncidentEventPermission`, and the matching case delete uses `CaseEventPermission`.

I didn't check the router-level setup, such as `include_router` calls or router dependencies in `api.py`. Those could apply an authentication or permission check to these routes even though the route definitions don't declare one. The 27 POST, PUT, PATCH and DELETE routes across the two files are otherwise all covered.

----- next turn -----

Yes, one of them is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event` in `src/dispatch/incident/views.py`). I've restored its check and added a test, but I haven't committed anything.

**The regression.** Commit `28c21e1e`, "refactor(incident): tidy custom event routes" (Sam Ortega, 2025-07-14), deleted the line `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from this route. The commit message describes it as a tidy-up, so the removal looks accidental. The sibling create, update and export event routes still have that check.

**The fix.** I put the same `IncidentEventPermission` dependency back on the route.

**The test.** `tests/incident/test_incident_event_permissions.py` finds the DELETE route in the incident router and asserts that `IncidentEventPermission` is among its permission dependencies. It passes with the fix. With the `src` change stashed it fails, so it will catch the check going missing again.

**The other two, not regressions.**
- `POST /{case_id}/resources/conversation` (`create_case_channel`) and `POST /{case_id}/resources` (`create_case_resources`) were added without a check in `ced74f33` and `f08a22b3`.
- They have never had a permission dependency, so they are a gap rather than a regression. Whether they should require `CaseEditPermission` is a design call for you. I left them alone, since you only asked about regressions.

I only ran the new test, not the full suite.

----- next turn -----

**Cause.** `restricted_case_filter` in `src/dispatch/database/service.py` lets non-admin users see too many cases. Its visibility condition had become a flat three-way OR:

```
open OR restricted OR participant-email == me
```

The `restricted` term on its own matches every restricted case, so a security team member (role member or none) saw all of them, including ones they don't take part in. The condition should be:

```
open OR (restricted AND participant-email == me)
```

**Commit.** `42699ebc`, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2025-09-02). It turned the `and_(...)` into separate OR terms, so what was meant as a tidy-up changed the logic. The incident filter, `restricted_incident_filter`, still has the correct `and_` form.

**Fix.** I put the `and_(restricted, email match)` back in the case filter, which is now the same shape as the incident filter. I didn't touch any tests. `tests/database` and `tests/case` pass (40 tests), but I haven't run the whole suite. The changes are uncommitted, along with the earlier incident permission fix and its test.

----- next turn -----



----- next turn -----

**Short answer:** the payload is masked in `redact_raw`, but only after it has already been committed unmasked. So yes, the unmasked payload is written to the database.

## Trace of `POST /api/v1/{organization}/signals/instances`

1. **Request handler.** `create_signal_instance` in `signal/views.py:70` is rate limited to 1000/minute.
   - It resolves the project.
   - It finds the signal definition by `externalId` or `variant` in `raw`, then falls back to the project's default definition. It returns 404 if there is none.
   - It then calls `signal_service.create_instance(...)` followed by `db_session.commit()`. A duplicate id returns 409.
   - The view never starts the processing flow, even though it takes a `BackgroundTasks` argument that it never uses.
   - There is also a bug in the lookup. `signal_definition`, `external_id` and `variant` are only assigned inside `if not signal_instance_in.signal:`. If the client sends a `signal`, the next `if not signal_definition:` raises `UnboundLocalError`.

2. **Persisting the instance.** `create_instance` (`signal/service.py:650`) copies `raw`, round-trips it through JSON and builds a `SignalInstance`. It uses the `raw` id as the primary key if there is one, which must be a UUID. The instance is saved with no filter action and no case.

3. **Pickup.** A separate worker picks the instance up. `cli.py:~985` selects instances where `filter_action IS NULL` and `case_id IS NULL`, oldest first, up to 500 per pass. `process_signal_batch` and `process_organization_signals` in `signal/flows.py` do the same. Each instance goes through `signal_instance_create_flow` in its own transaction.

4. **Flow, in order** (`signal/flows.py:44`):
   - **Redaction:** `signal_instance.raw = redact_raw(signal_instance.raw)`.
   - **Entity extraction:** entity types attached to the signal plus the `all`-scoped ones.
   - **Filtering:** `signal_service.filter_signal` (`signal/service.py:866`). It applies snooze first, and only if not snoozed it applies dedup, which has a default window grouping instances together.
     - If either filter acts, the instance is marked filtered, linked to the existing case if there is one, and the Slack signal message is updated if needed. The flow stops there.
     - Otherwise `filter_action` is set to `none`.
   - **Early returns, no case:** canary instances, and signals with `create_case` off.
   - **Case creation:** the case type, priority, oncall service and conversation target come from the instance, then the signal, then the case type. The flow resolves the assignee from oncall, builds a `CaseCreate` with `Visibility.open` and calls `case_service.create`. It links the case to the instance, commits, and continues into the case creation flow.

## Masking details

- **Function:** `redact_raw` in `signal/redaction.py`, called from `flows.py:60`. It is the only call site.
- **Behaviour:**
  - It returns a copy.
  - It matches key names case-insensitively, at any depth, inside dicts and lists.
  - It replaces the whole value with `"[REDACTED]"`.
  - It does not look at string values, only at key names.
- **Default keys** (`SIGNAL_REDACTED_RAW_FIELDS`, `config.py:98`): `password`, `secret`, `api_key`, `session_token`, `authorization`. They are overridable with a comma-separated env var of the same name.
  - Matching is exact. `client_secret`, `token`, `apiKey` and `access_token` are not masked by default.

## Is the unmasked payload written to the database?

Yes, in two ways:

- **Committed before redaction.** The view commits the full `raw` at step 1 or 2. It stays in the database until the worker redacts it. That window lasts until the next worker pass, which could be about a minute or longer if there is a backlog.
- **Never redacted on some paths.**
  - The view path persists before redaction, so a failure in the worker leaves it unmasked. `process_signal_batch` and the `cli.py` loop roll back on error, so the instance is retried, but a persistent failure leaves the unmasked `raw` in place.
  - `update_instance` (`signal/service.py:726`) overwrites `raw` with a fresh unmasked copy and does not call `redact_raw`.
  - `create_signal_instance` at `signal/service.py:162` and the creation at `flows.py:258` create instances without redaction. Both rely on the same later flow, and nothing masks them on creation.

Redaction also runs before the entity step, so entities are extracted from the masked payload. A sensitive value in an unmasked key can still become an entity.

I haven't changed any code. The fix would be to redact before the first commit, in `create_instance`. That would also cover the other creation paths.

----- next turn -----

**Responsible change:** commit `beb60cc4`, "perf(entity): stop at the first JSONPath match" (Sam Ortega, 2025-09-02). It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`, so only the first match of each JSONPath could become an entity.

**Fix:** I removed the `[:1]` slice and the comment that justified it, so `find_entities` once again goes through every match. This is the same code as before `beb60cc4`, and the diff against that commit's parent is empty for this file.

**Tests:** CI was red because of `tests/entity/test_entity_service.py::test_find_entities_with_field_only`, which expected 2 entities and got 1. `python -m pytest tests/entity` now gives 11 passed. I didn't change any tests and I haven't run the rest of the suite.

The change is uncommitted, together with the earlier fixes in `src/dispatch/database/service.py` and `src/dispatch/incident/views.py` and the new `tests/incident/` test.

----- next turn -----

**Why unrelated instances were grouped:** the signal flow masks the payload first. `redact_raw` turns `session_token` into `"[REDACTED]"`, and entity extraction runs right after. The JSONPath then matches that placeholder and makes an entity with the value `[REDACTED]`. Every instance of the signal therefore gets the same entity, and the dedup filter on that entity type puts them all in one case.

**Fix:** in `find_entities` (`src/dispatch/entity/service.py`), a JSONPath match whose value is the redaction mask is now skipped. It imports `MASK` from `dispatch.signal.redaction`. The masking itself is unchanged.

**Coverage:** every place that extracts entities from a payload calls `find_entities`:
- the signal flow
- `entity_type/flows.py`
- `entity_type/service.py`, which re-extracts from stored instances

So the one check covers all of them. It also covers stored instances whose `raw` was already masked.

**Test:** `test_find_entities_ignores_masked_values` in `tests/entity/test_entity_service.py`. I only added it and changed no existing test. It redacts a payload with a top-level `session_token`, a nested list with a `password` key and a normal `user` key. It expects only `alice`, the normal value, to become an entity.
- Without the fix it fails.
- `python -m pytest tests/entity` gives 12 passed, and `tests/signal` also passes.

**Limits:**
- A genuine payload value that is literally `[REDACTED]` would also be skipped, which seems an acceptable trade.
- Unmasked values still get extracted if the worker hasn't redacted them yet, as I described earlier, because the view commits before masking.
- Everything is still uncommitted.

----- next turn -----

## Recap

**1. Permission review (case and incident APIs)**
- Before my changes, five data-changing handlers had no `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, because anyone may report a case or an incident.
- `delete_custom_event` was a regression. Commit `28c21e1e` removed its `IncidentEventPermission` check. I restored it in `src/dispatch/incident/views.py`. The new test `tests/incident/test_incident_event_permissions.py` fails if the check goes missing again.
- `create_case_channel` and `create_case_resources` look like an original gap, not a regression. I left them unchanged. Whether they should require `CaseEditPermission` is your design call.
- I did not check whether a router-level or `api.py` dependency covers any of these routes.

**2. Restricted cases visible to members**
- `restricted_case_filter` in `src/dispatch/database/service.py` had been flattened to `open OR restricted OR participant-email == me`. The bare `restricted` term matched every restricted case.
- Commit `42699ebc` introduced it. I restored `open OR (restricted AND participant-email == me)`.
- `tests/database` and `tests/case` pass. I added no new test for this.

**3. Signal instance trace and masking**
- The `POST` handler stores the instance and commits it with the full `raw` payload. A separate worker later runs `signal_instance_create_flow`, which masks the payload, extracts entities, then applies snooze and dedup filters. It either links the instance to an existing case or creates a new one.
- Masking is done by `redact_raw` in `dispatch.signal.redaction`. It masks by key name, case-insensitively, at any depth. The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- The unmasked payload is written to the database, because the view commits before the worker masks it. `update_instance` also writes unmasked data. The masking was introduced in commit `d2675cf4`.

**4. Entity extraction bugs**
- Commit `beb60cc4` made `find_entities` keep only the first JSONPath match. I removed the `[:1]` slice and `tests/entity` went green.
- Masked values were becoming entities with the value `[REDACTED]`, so unrelated instances were deduplicated into one case. `find_entities` now skips values equal to the mask. I added `test_find_entities_ignores_masked_values`.
- All changes are uncommitted. I did not run the whole test suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4