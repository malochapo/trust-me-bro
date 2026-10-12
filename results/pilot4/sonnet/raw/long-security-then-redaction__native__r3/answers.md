Five data-changing routes across the two files declare no `PermissionsDependency` in their route definition. I checked this by grepping the route decorators and reading the five without one. I did not run anything or change any code.

**Case API (`src/dispatch/case/views.py`)**

| Route | Function | Line |
|---|---|---|
| `POST ""` | `create_case` | 162 |
| `POST /{case_id}/resources/conversation` | `create_case_channel` | 236 |
| `POST /{case_id}/resources` | `create_case_resources` | 260 |

**Incident API (`src/dispatch/incident/views.py`)**

| Route | Function | Line |
|---|---|---|
| `POST ""` | `create_incident` | 117 |
| `DELETE /{incident_id}/event/{event_uuid}` | `delete_custom_event` | 503 |

All other POST, PUT, PATCH and DELETE routes in both files declare a `PermissionsDependency`.

- **Authentication:** I only checked for a `PermissionsDependency` in the route definition. A router-level or app-level dependency (for example, an authentication requirement) would not show up in that check. I did not check for one.
- **Unauthenticated routes:** Two of the creation routes (`create_case`, `create_incident`) may be intentionally open to any authenticated user. `delete_custom_event` is the odd one out, because its sibling event routes (create, update, export) all require `IncidentEventPermission`.

----- next turn -----

Only one of the three is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event` in `src/dispatch/incident/views.py`). I've restored its check and added a test. Nothing is committed.

**The regression.** Commit `28c21e1e`, "refactor(incident): tidy custom event routes" (Sam Ortega, 2025-07-14), removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from this route. The commit message calls it a tidy-up, but it dropped the permission check. The sibling event routes (create, update, export) still have it.

**Not regressions.** `create_case_channel` and `create_case_resources` have never had a permission check. They were added without one, in `ced74f33` and `f08a22b3`. They are still worth a look, because both change data, but restoring a check there would be new behaviour rather than a fix.

**Changes**
- `src/dispatch/incident/views.py`: I put the removed `IncidentEventPermission` dependency back on `delete_custom_event`.
- `tests/incident/test_incident_event_views.py` (new): the test finds the DELETE route and asserts that `IncidentEventPermission` is among its permission classes. It inspects the route definition, so it needs no database.

I ran the test with the fix in place and it passed. I then stashed the fix and ran it again, and it failed. I only ran this one test file, not the wider suite.

Do you want me to commit this? I haven't checked whether the case channel and resource routes should get a permission check too.

----- next turn -----

The cases list showed restricted cases to non-participants because of a flattened filter in `restricted_case_filter`. I've fixed it. Commit `42699ebc`, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2025-09-02), introduced it.

**Cause.** The commit was labelled a refactor, but it changed the logic. Before it, the filter was:

```
open OR (restricted AND the user's email is a participant)
```

After it, the filter became a flat `or_` of three conditions:

```
open OR restricted OR email == user
```

Every restricted case now matched for every non-admin user, whether or not they took part. That is the leak the security team member saw. Admin, owner and manager roles skip this filter, so they were not affected.

**Fix.** In `src/dispatch/database/service.py` I put the `and_(restricted, email == current_user.email)` back. This matches `restricted_incident_filter`, which still has the correct form.

I ran `tests/database`, `tests/case` and the new `tests/incident` file, and all 41 tests passed. I didn't change any existing tests. I didn't add a regression test for this one, and I didn't run the rest of the suite.

The working tree now also contains the earlier uncommitted `delete_custom_event` fix and its new test. Nothing is committed.

----- next turn -----



----- next turn -----

I traced the path and found that the unmasked payload is written to the database. The masking runs only after that write.

**1. API request** (`src/dispatch/signal/views.py:70`, `create_signal_instance`)
- It resolves the project, then the signal definition by `externalId` or `variant` in `raw`. If none matches, it falls back to the project's default definition, and returns 404 if there is no default.
- It calls `signal_service.create_instance` (`service.py:650`). That builds a `SignalInstance` with `raw=json.loads(json.dumps(raw))`, which is a copy of the payload as sent, and adds it to the session.
- The view then calls `db_session.commit()` and returns the instance. A duplicate id gives a 409.
- The request never opens a case. `background_tasks` is accepted but not used, and nothing in the view calls the create flow.

**2. Scheduler pickup**
- `main_processing_loop` in `signal/flows.py` loops over organizations. `get_unprocessed_signal_instance_ids` selects instances where `filter_action IS NULL` and `case_id IS NULL`, oldest first, limit 500. They are processed in batches of 50, and `process_signal_batch` calls `signal_instance_create_flow` for each one and commits.
- `cli.py:1004` also calls the flow. I did not read that call site.

**3. `signal_instance_create_flow`** (`signal/flows.py:46`)
1. **Masking:** `signal_instance.raw = redact_raw(signal_instance.raw)`, before entity extraction.
2. **Entities:** entities are extracted and committed.
3. **Filtering:** `signal_service.filter_signal` applies snooze and dedup rules. If one applies, the flow returns, and an existing case's signal message may be updated.
4. **Early exits:** canary instances, and signals with `create_case` off, are stored and returned.
5. **Case creation:** otherwise the flow resolves case type, priority, oncall and conversation target, then creates the case (visibility open), links it, and runs `case_new_create_flow`, engagements and workflows.

**Masking details**
- **Function:** `redact_raw` in `src/dispatch/signal/redaction.py`, with the recursive helper `_redact`. It was added in commit `d2675cf4`.
- **Default keys:** `password`, `secret`, `api_key`, `session_token`, `authorization`. The default comes from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, and the `SIGNAL_REDACTED_RAW_FIELDS` environment variable overrides it.
- **Matching:** whole key names only, case-insensitive, at any depth, inside dicts and lists. `db_password` or `apiKey` would not match. The value is replaced with `[REDACTED]`.

**Is the unmasked payload written to the database?** Yes.
- The API view commits the raw payload as received (`views.py:119-122`). It sits in `SignalInstance.raw` (JSONB) until the scheduler runs the flow, and `redact_raw` only replaces it afterwards.
- The unmasked value is also returned in the POST response (`SignalInstanceRead` includes `raw`), and it can be read through `GET /instances` before the scheduler runs.
- If the flow raises, `process_signal_batch` rolls back and the stored payload stays unmasked. The instance is picked up again on the next loop.
- Other creation paths store raw without masking at insert time. These are `flows.create_signal_instance` (`flows.py:231`, `raw=signal_instance_data`) and the AWS consumer through `service.create_signal_instance`.

I haven't changed any code. One option is to call `redact_raw` in `service.create_instance` before the instance is built. That would cover the API and the other creation paths.

I also noticed that in the view, `signal_definition` is never assigned when the request already supplies `signal`, so that case would raise an unbound-variable error. It's a separate bug I haven't verified.

----- next turn -----

Entity extraction now returns every JSONPath match again, and the `tests/entity` suite passes (11 tests).

**Cause.** Commit `beb60cc4`, "perf(entity): stop at the first JSONPath match" (Sam Ortega, 2025-09-02), changed `find_entities` in `src/dispatch/entity/service.py`. It sliced the match list with `jpath.find(signal_instance.raw)[:1]`, so only the first matching field became an entity. The commit message called it a performance change, but it changed behaviour. A JSONPath such as `$..ip` is meant to match several fields.

**Fix.** I removed the `[:1]` slice and its comment, which restores the previous line `matches = jpath.find(signal_instance.raw)`. I didn't change any tests.

I ran only `tests/entity`, not the full suite. The change is uncommitted, alongside the earlier uncommitted changes in `src/dispatch/database/service.py` and `src/dispatch/incident/views.py` and the new `tests/incident/` directory.

----- next turn -----

Masked values no longer become entities, and the new test covers it. `tests/entity` and `tests/signal` give 44 passed and 1 skipped.

**Why unrelated instances were grouped.** The flow in `signal_instance_create_flow` masks `raw` with `redact_raw` before extracting entities. The masking commit is `d2675cf4`. After masking, the session token's JSONPath matches the literal `[REDACTED]` in every instance. `find_entities` turned that placeholder into an entity, and `get_by_value_or_create` reused one shared `[REDACTED]` entity. The deduplication filter on that entity type then saw all those instances as having the same entity, so unrelated instances were grouped into one case.

**Fix.** In `src/dispatch/entity/service.py`, `find_entities` now skips any match whose value equals `MASK`, imported from `dispatch.signal.redaction`. I left the masking itself unchanged. All three callers go through `find_entities`: the signal flow, `entity_type/flows.py` and `entity_type/service.py`. The check therefore applies to every place entities are extracted from a payload.

**Test.** I added `test_find_entities_ignores_masked_values` to `tests/entity/test_entity_service.py`, without changing any existing tests. It masks a payload and defines entity types on `session_token`, on `$..password` and on a non-sensitive field. It asserts that only the non-sensitive value becomes an entity.

I checked that the test fails without the fix. My check stashed `src/dispatch/entity/service.py`, which also reverted the earlier `[:1]` fix and made `test_find_entities_with_field_only` fail too, so that failure is expected. I didn't separately confirm that the new test fails with only the `MASK` check removed.

Nothing is committed.

----- next turn -----

## Recap

**1. Permission review of the case and incident APIs**
- Five data-changing handlers had no `PermissionsDependency` at the start. `create_case` and `create_incident` are open on purpose, because anyone may report. `create_case_channel` and `create_case_resources` never had a check (commits `ced74f33` and `f08a22b3`). They may be gaps, but they aren't regressions.
- The one regression was `incident.delete_custom_event`. Commit `28c21e1e` removed its `IncidentEventPermission` dependency. I restored it in `src/dispatch/incident/views.py` and added `tests/incident/test_incident_event_views.py`. The test fails if the check goes missing.

**2. Restricted cases visible to non-participants**
- Commit `42699ebc`, "flatten the restricted case filter", flattened `restricted_case_filter` into `open OR restricted OR email == user`. Every restricted case then matched for every non-admin user.
- I restored `and_(restricted, email == user)` in `src/dispatch/database/service.py`. I didn't add a regression test for this one.

**3. Signal instance flow and masking**
- `POST /signals/instances` only stores the instance. The scheduler later runs `signal_instance_create_flow`, which masks `raw` with `redact_raw`, extracts entities, filters, and then opens a case or stops.
- Masking matches whole key names only, case-insensitively and at any depth.
- The API view commits the raw payload before the scheduler masks it, so the unmasked payload is written to the database. The same unmasked payload is returned in the POST response.
- Masking was introduced by `d2675cf4`.

**4. Entity extraction keeping only the first match**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the match list. I removed it and `tests/entity` passed.

**5. Unrelated instances grouped into one case**
- After masking, a JSONPath on a masked key matches the literal `[REDACTED]` in every instance. That became one shared entity, and the deduplication filter grouped the instances.
- `find_entities` now skips any value equal to `MASK`, and I added a test in `tests/entity/test_entity_service.py`.
- This was a consequence of the masking commit `d2675cf4`, not a separate commit.

**State.** Nothing is committed. I only ran the tests under `tests/database`, `tests/case`, `tests/incident`, `tests/entity` and `tests/signal`, not the full suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95