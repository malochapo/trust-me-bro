Seven mutating routes in these two files have no `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
3. `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

That is five routes. The other mutating routes in both files declare a `PermissionsDependency`.

I checked only the route decorators. Both files use a plain `APIRouter()` with no router-level dependencies, so the decorators are the full story within each file. I did not check how the routers are mounted in the app, which could add auth at a higher level. I also did not check whether the function bodies call a permission check themselves. No code was changed.

----- next turn -----

I found one regression and fixed it. The other mutating routes without a check were never guarded, so they are not regressions.

**The regression: `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`)**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line. The commit touched nothing else.
- Every sibling event route (create, update, export) still declares `IncidentEventPermission`.
- I restored the line in `src/dispatch/incident/views.py`. It is the only code change.

**Regression test: `tests/incident/test_incident_event_views.py`**
- The test finds the DELETE route on the incident router and asserts it declares `IncidentEventPermission` through `PermissionsDependency`.
- With the fix it passes. With the check temporarily removed it fails, and I restored the fix afterwards.
- `python -m pytest tests/incident tests/case` runs 16 tests, all passing.

**Not regressions**
- `POST /case/{case_id}/resources` and `POST /case/{case_id}/resources/conversation` have never had a permission declaration. Git history shows them added without one, so I left them alone. Whether they should have one is a design call for you.
- `POST` on the case and incident collections (create case, create incident) are the open-by-design routes you mentioned.

I did not check whether the case-side resource routes should use an existing permission, such as `CaseEditPermission`. I can add that if you want it.

----- next turn -----

The cause was a dropped `and_` in `restricted_case_filter` (`src/dispatch/database/service.py`). It made every restricted case visible to non-admin users, whether or not they were a participant.

**Introducing commit:** `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, Sep 2 2025). It was meant as a cleanup, but it removed the `and_(...)` that tied the restricted case to the user's participation. The incident filter still has that wrapper.

**Fix:** I restored the `and_` so the case branch matches the incident filter: a restricted case is visible only when the user is a participant. This is the only change to that file.

**Verification**
- `python -m pytest tests/database/test_service.py tests/case` passes, 40 tests.
- The existing `test_restricted_case_filter_with_test_data` fails on the buggy HEAD and passes with the fix. I did not modify any existing tests.

**Other changes still in the working tree from earlier:** the restored `IncidentEventPermission` check in `src/dispatch/incident/views.py`, and the new `tests/incident/test_incident_event_views.py`. Nothing has been committed.

----- next turn -----



----- next turn -----

Nothing was changed. The short answer: the payload is masked asynchronously, after the POST has already saved it, and the unmasked payload is written to the database in the meantime.

**1. The POST request** (`src/dispatch/signal/views.py:70-128`, `create_signal_instance`)

- It resolves the project and the signal definition, using `externalId` or `variant` from `raw` and falling back to the default definition. If none exists, it returns 404.
- It calls `signal_service.create_instance` (`src/dispatch/signal/service.py:650`) and commits. `create_instance` stores `raw` as a JSON round-trip of the request body, with no masking.
- The response is `SignalInstanceRead`. `raw` is declared on `SignalInstanceBase` (`src/dispatch/signal/models.py:394`), so the response most likely echoes the raw payload, unmasked. I did not check whether `SignalInstanceRead` inherits from that base.
- The route does not call the processing flow. It returns once the row is committed.

**2. Masking happens later, in the processing flow** (`src/dispatch/signal/flows.py:50-60`, `signal_instance_create_flow`)

The first thing it does after loading the instance is:

```python
# mask sensitive values before entities are extracted from the payload
signal_instance.raw = redact_raw(signal_instance.raw)
```

This is the only place masking happens. Nothing in the POST path or `create_instance` calls it.

**3. Where the masking function lives** (`src/dispatch/signal/redaction.py`)

- `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` returns a copy with the value of every matching key replaced by `"[REDACTED]"`.
- Matching is case-insensitive and applies at any depth, inside nested dicts and lists.
- The default keys come from `src/dispatch/config.py:98-102`, configured by the `SIGNAL_REDACTED_RAW_FIELDS` environment variable: `password`, `secret`, `api_key`, `session_token`, `authorization`.
- Only key names are matched. A sensitive value under any other key is not masked.

**4. Who runs the flow**

- The background loop `process_organization_signals` (`src/dispatch/signal/flows.py:~430-468`) reads up to 500 unprocessed instances per org, where `filter_action` and `case_id` are both null. It processes them in batches of 50 and runs every `LOOP_DELAY` (60 s).
- There is also a CLI path in `src/dispatch/cli.py:~1004` that calls the same flow.
- Instances are created through the API and through the AWS plugin (`src/dispatch/plugins/dispatch_aws/plugin.py`). Both go through `create_instance`, so both store unmasked `raw` first.

**5. Order of operations inside the flow, and where it ends**

1. Redact `raw` in memory.
2. Find entities from the redacted `raw` (`entity/service.py:290` uses `jpath.find(signal_instance.raw)`), so a masked secret cannot become an entity. This commits only if entity types exist.
3. `filter_signal` (snooze, then dedup). It always commits at the end, so the redacted `raw` is persisted here.
4. If filtered, return. The instance keeps its redacted payload.
5. If canary or `create_case` is false, return. The redacted payload is already committed.
6. Otherwise create the case, run engagements and workflows. The case gets the redacted payload.

**6. Is the unmasked payload written to the database?** Yes, in two windows:

- **Between POST and processing.** `create_instance` commits the unmasked `raw` to the `signal_instance.raw` JSONB column. It stays there until the scheduler reaches the row, up to a minute or longer if the backlog is large.
- **If processing fails before `filter_signal` commits.** `process_signal_batch` rolls back on exception, so the in-memory redaction is lost. The row stays unprocessed and the unmasked payload remains in the database. The loop retries it each cycle, and any repeated failure leaves it unmasked.

The code I read does not mask anything at write time. The redacted value is only committed once `filter_signal` runs.

**Other things I noticed**

- `update_instance` (`signal/service.py:~728`) writes `raw` without masking. I found no callers for it in the signal code. The only callers I found are in the plugin and workflow modules, which are different functions.
- Nothing in `tests/` references `redact_raw` or `SIGNAL_REDACTED_RAW_FIELDS`, so there is no test covering the masking.
- The AI prompt (`ai/service.py:317`) and the Slack export (`plugins/dispatch_slack/plugin.py:155`) read `raw` from the stored row. They get the masked copy only if processing has already run.

----- next turn -----

The entity tests are green again. The fix is in `src/dispatch/entity/service.py`. The change responsible was `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, Sep 2 2025). It added `[:1]` to `jpath.find(...)`, which discarded every match after the first. I removed the slice and its comment, so `find_entities` again yields one entity per matching string field.

**Verification**
- Before the fix, `python -m pytest tests/entity -q` gave 1 failed, 10 passed. The failure was `test_find_entities_with_field_only`, which expected 2 entities and got 1.
- After the fix, `python -m pytest tests/entity -q` gives 11 passed.
- I did not change any tests.

**Working tree:** the earlier changes are still uncommitted (the restored `and_` in `database/service.py`, the restored `IncidentEventPermission` check and its new test in `incident/`). I have not run the full suite. Nothing has been committed.

----- next turn -----

The cause was that the masked value itself became an entity. The fix is in `find_entities`, and the new test fails without it.

**Why instances grouped:** The flow redacts `raw` (`signal/flows.py:60`) before it extracts entities. For a JSONPath that points at a masked field, the match is the string `"[REDACTED]"`. That match became an entity, so every instance got the same entity, and the deduplication filter grouped them.

**Fix** (`src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression`):
- Extraction now runs against `redact_raw(signal_instance.raw)`, and any match equal to `MASK` is skipped.
- The guard is in `find_entities` rather than the flow because `find_entities` is also called from `entity_type/service.py:95` and `entity_type/flows.py:29`, which work from stored payloads. Those can hold unredacted values for instances the flow has not processed yet.
- `redaction.py` is unchanged, so the masking itself is as it was.
- The regex entries in `entity_type_pairs` are never used for extraction. Only the JSONPath branch exists, so this guard covers every extraction path.

**Test:** `test_find_entities_never_extracts_masked_values` in `tests/entity/test_entity_service.py`. It appends a new test and changes no existing ones. A `session_token` JSONPath yields no entity, and a non-sensitive `reporter` field still yields one.

**Verification**
- Without the mask check, the new test fails.
- With the fix: `tests/entity`, `tests/signal`, and `tests/entity_type` give 50 passed, 1 skipped.

**Working tree:** `src/dispatch/entity/service.py` now also contains the earlier `[:1]` revert, plus this change. Nothing is committed. The uncommitted changes from earlier are still there too: the `database/service.py` filter fix, the `incident/views.py` permission restore, and the new `tests/incident/` test.

----- next turn -----

Here is the recap for the weekly report. Nothing is committed, and the full test suite has not been run. Only the test directories I touched were run.

**1. Unguarded data-changing routes and the restored check**
- Before my changes, five POST/PUT/PATCH/DELETE handlers had no `PermissionsDependency`: `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident`, and `incident.delete_custom_event`.
- `incident.create_incident` is open on purpose, since anyone may report an incident. `case.create_case` is also open by design, and the report-wide intent note covers it.
- `case.create_case_channel` and `case.create_case_resources` never had a check, so they are not regressions. Whether they should carry `CaseEditPermission` is still an open question.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") deleted its `IncidentEventPermission` dependency. I restored it in `src/dispatch/incident/views.py`. A new test, `tests/incident/test_incident_event_views.py`, fails if the check goes missing again.

**2. Cases list showing restricted cases to non-participants**
- The cause was `restricted_case_filter` in `src/dispatch/database/service.py`. The `and_` tying a restricted case to the user's participation had been dropped. Every restricted case then matched for non-admin roles.
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter") introduced it. It was framed as a cleanup. I restored the `and_` to match the incident filter.
- `tests/database/test_service.py::test_restricted_case_filter_with_test_data` fails on the buggy version and passes with the fix. No existing tests were changed.

**3. Entity extraction keeping only the first match**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath match, so only one entity per type was kept.
- I removed the slice in `src/dispatch/entity/service.py`. `tests/entity` failed before and passes after.

**4. Masked values becoming entities**
- Signal instances from the "GitHub: Personal access token exposed" signal were grouping because the masked value `"[REDACTED]"` became an entity. Every instance then shared that entity, and the dedup filter grouped them.
- The fix is in `find_entities` (`src/dispatch/entity/service.py`). It matches JSONPaths against the redacted payload and skips any match equal to the mask. I left the masking itself unchanged.
- New test: `test_find_entities_never_extracts_masked_values`. It fails without the guard. `tests/entity`, `tests/signal`, and `tests/entity_type` give 50 passed and 1 skipped.

**5. Masking**
- The redaction lives in `redact_raw` in `src/dispatch/signal/redaction.py`. It is called from the signal instance create flow, `signal_instance_create_flow`.
- The unmasked payload is written to the database. `create_instance` commits the raw payload before the flow masks it, and it stays unmasked until the scheduled job processes the row.
- Masking was introduced in commit `d2675cf4` ("feat(signal): mask sensitive raw fields before processing").

**Uncommitted changes in the working tree**
- `src/dispatch/database/service.py`
- `src/dispatch/entity/service.py`
- `src/dispatch/incident/views.py`
- `tests/incident/` (new)
- `tests/entity/test_entity_service.py` (one test appended)

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4