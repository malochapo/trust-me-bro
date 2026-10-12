Five write routes have no `PermissionsDependency`: three in the case API and two in the incident API.

**Case API (`src/dispatch/case/views.py`)**
- `POST ""` (`create_case`), line 162
- `POST /{case_id}/resources/conversation`, line 236
- `POST /{case_id}/resources`, line 260

**Incident API (`src/dispatch/incident/views.py`)**
- `POST ""` (`create_incident`), line 117
- `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`), line 503

I checked each POST, PUT, PATCH and DELETE decorator by reading its full route definition, not just the nearby lines. Every other write route declares a `PermissionsDependency` in its `dependencies=` list. I did not change any code.

----- next turn -----

One of the five unprotected routes was a regression, and it is now restored with a test.

**The regression:** `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`) lost its `PermissionsDependency([IncidentEventPermission])` in commit `28c21e1e` ("refactor(incident): tidy custom event routes"). That commit was a one-line deletion of the `dependencies=` line; the other routes in that file kept their checks. The route is now guarded again by the same permission it had before.

**Not regressions:** The two case resource routes, `POST /case/{case_id}/resources` and `POST /case/{case_id}/resources/conversation`, were added without a permission check (commits `f08a22b3` and `ced74f33`) and never had one. That is an oversight rather than a removal, so I left them alone. You may still want to decide whether they should have a check. The two create routes (`POST` on cases and incidents) are the open-by-design ones you mentioned.

**Changes:**
- `src/dispatch/incident/views.py`: added the `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line back to the delete route.
- `tests/incident/test_incident_event_permissions.py` (new): finds the DELETE route on the incident router and asserts `IncidentEventPermission` is among its permission classes. It fails with the fix stashed and passes with it applied.

**Test results:** `python -m pytest` on the new test and `tests/case/test_case_event_views.py` gives 5 passed. I did not run the full suite.

The changes are uncommitted in the working tree.

----- next turn -----

The cause was in `restricted_case_filter` (`src/dispatch/database/service.py`). Non-admin users, including the security team's members, could see every restricted case, not only the ones they participate in.

**Introduced by:** commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). The refactor removed an `and_(...)` that tied the restricted-visibility branch to the participant email check. The filter then read `visibility == open OR visibility == restricted OR participant email matches`, so the middle term matched any restricted case.

**Fix:** I restored the grouping so restricted cases require the participant match, as the incident version already does. This is a 3-line change in `src/dispatch/database/service.py`.

**Verification:**
- `tests/database/test_service.py` and `tests/case/test_case_service.py`: 35 passed with the fix.
- Without the fix, `test_restricted_case_filter_with_test_data` fails and the other 34 pass. So the existing test does catch this bug. I didn't modify any tests.

**Still uncommitted:** this change, plus the two from the previous turn (the restored `IncidentEventPermission` check and its new test).

----- next turn -----



----- next turn -----

The sensitive-value masking happens in `signal_instance_create_flow`, which runs after the POST has already stored the unmasked payload. The POST handler does not mask anything.

**Path from the request to a case or a filter:**

1. **`POST /api/v1/{organization}/signals/instances`** is `create_signal_instance` in `src/dispatch/signal/views.py:70-125`. It resolves the signal definition (by external id or variant, falling back to the project default), then calls `signal_service.create_instance` and commits (`views.py:121`). It returns 404 if no definition exists and 409 on a duplicate id. The route declares a `background_tasks` parameter, but the body never uses it, so the POST does not start processing.
2. **`signal_service.create_instance`** (`src/dispatch/signal/service.py:650-707`) builds the `SignalInstance` with `raw=json.loads(json.dumps(raw))` at line 680. This is a JSON round-trip only. Nothing is masked here, so the full payload is written to the `raw` JSONB column (`models.py:239`).
3. **Processing happens later, in a worker.** The worker selects rows where `filter_action` and `case_id` are both null (`signal/service.py:900-915`). The loop in `src/dispatch/cli.py` (around lines 980-1010) calls `signal_flows.signal_instance_create_flow` for each row. `flows.process_organization_signals` and `flows.main_processing_loop` in `src/dispatch/signal/flows.py` do the same. I did not find a caller for `main_processing_loop` in `src`.
4. **`signal_instance_create_flow`** (`src/dispatch/signal/flows.py:46-228`):
   - **Masking, line 60:** `signal_instance.raw = redact_raw(signal_instance.raw)`. This is the first step, before entity extraction and before the canary check.
   - **Entities, lines 63-75:** entity types are matched against the redacted `raw` through JSONPath in `entity/service.py:290`. If any entity types apply, the flow commits at line 75, which persists the redacted payload.
   - **Filtering, lines 78-100:** `signal_service.filter_signal` runs snooze and dedup. If an action applies, it commits (`service.py:896`) and the flow returns without a case.
   - **Canary, lines 103-104:** the instance is stored and returned without a case.
   - **No case creation, lines 106-107:** if the signal's `create_case` is false, the flow returns without a case.
   - **Case creation, lines 110-216:** a `CaseCreate` is built from the signal's name and description, with `visibility=open`. Then `case_service.create`, the case-flow setup, engagements, and workflows run. The `raw` is not copied into the case.

**Masking function and defaults:**

- The function is `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` in `src/dispatch/signal/redaction.py:10`. It recurses through dicts and lists at any depth. Values under a matching key become the string `"[REDACTED]"`. Other values pass through unchanged.
- Matching is exact on the key name, after trimming and lowercasing. It is not a substring match.
- The default list is set in `src/dispatch/config.py:98-102` and can be overridden with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable. The defaults are `password`, `secret`, `api_key`, `session_token`, and `authorization`.
- Keys such as `apiKey`, `api-key`, or `token` are not matched by the default list, because matching is an exact comparison after lowercasing.

**Is the unmasked payload written to the database?** Yes. The POST commits the full payload (`views.py:121`, via `service.py:680`). It stays unmasked until a worker processes the row and runs `flows.py:60`. The redacted version is persisted when the flow commits (`flows.py:75` or `service.py:896`). Until then, the unmasked payload is in the `raw` column and is returned in the POST response (`SignalInstanceRead`).

**Things to note:**

- The unmasked window lasts from the POST commit until the worker processes the row. The worker runs on a loop, so this is more than a few seconds.
- If the `raw` is modified after masking, the redacted version is the one that gets saved.
- Masking runs before entity extraction. A JSONPath entity type that targets a masked key, such as `password`, will get `[REDACTED]` instead of the real value.
- `redact_raw` is not applied on the other ingest path, the AWS plugin (`src/dispatch/plugins/dispatch_aws/plugin.py:102-135`), which calls `create_instance` directly. I did not trace whether that path is masked anywhere else.
- Other readers of `raw` (`ai/service.py:212` and `317`, Slack's JSON export at `dispatch_slack/plugin.py:155`) see whatever is stored at the time they run.

I did not change any code.

----- next turn -----

The change responsible is `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02). It added `[:1]` to the JSONPath match in `find_entities` (`src/dispatch/entity/service.py:289`), so each entity type produced at most one entity, even when its JSONPath matched several fields. For example, `asset[*].id` returned only the first ID.

I reverted that line to `matches = jpath.find(signal_instance.raw)`. I did not change any tests.

**Verification:** `python -m pytest tests/entity -q` gives 11 passed. Before the fix, `test_find_entities_with_field_only` failed (`assert 1 == 2` on the `asset[*].id` case).

**Still uncommitted:** this change, plus the earlier ones in `src/dispatch/database/service.py`, `src/dispatch/incident/views.py`, and the new `tests/incident/` file.

----- next turn -----

Unrelated instances were grouped because a masked value was turned into an entity. Once the token is masked, every instance's entity has the same value, `"[REDACTED]"`, so the deduplication filter matches them all to one case. I fixed this in `find_entities` and added a regression test. The masking itself is unchanged.

**Cause:** the signal flow masks `raw` before it calls `find_entities` (`src/dispatch/signal/flows.py:60`). The entity type's JSONPath still matches the masked key, and `find_entities` accepted the string `"[REDACTED]"` as the entity value. Other callers, such as the entity-type recalculation paths (`entity_type/service.py:95` and `entity_type/flows.py:29`), could pass an unmasked `raw`, so the masking in the flow didn't cover them.

**Fix (`src/dispatch/entity/service.py`):**
- `find_entities` now runs the JSONPath against `redact_raw(signal_instance.raw)`, so every caller gets masked values.
- Matches whose value equals `MASK` are skipped.

**Test:** I added `tests/entity/test_entity_redaction.py` with three cases:
- A masked top-level key yields no entity, including with a `$..*` wildcard.
- A value nested under a masked key (`authorization.token`) yields no entity.
- An unmasked value still yields an entity.

With the fix, the three tests pass. With the two changes reverted, two of them fail, which confirms they cover the bug. `tests/entity` and `tests/signal` pass (46 passed, 1 skipped). I did not change any existing tests.

**Behavior change:** a payload value that is literally `"[REDACTED]"` under an unmasked key is now also skipped as an entity. I think that is acceptable, but say so if you'd rather compare by masked key path.

**Uncommitted:** this change, plus the earlier ones in `src/dispatch/entity/service.py` (the `[:1]` revert), `src/dispatch/database/service.py`, `src/dispatch/incident/views.py`, and the new test files under `tests/incident/` and `tests/entity/`.

----- next turn -----

## Recap

**Security review (case and incident write routes)**

Before my changes, five handlers changed data without a `PermissionsDependency`:
- `case.create_case` (open by design: anyone may report a case)
- `case.create_case_channel` and `case.create_case_resources` (never protected, so not a regression; whether they should be is still open)
- `incident.create_incident` (open by design: anyone may report an incident)
- `incident.delete_custom_event`: a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its permission check.

I restored `IncidentEventPermission` on `delete_custom_event` and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again.

**Restricted cases shown to non-participants**

`restricted_case_filter` in `src/dispatch/database/service.py` let every non-admin see every restricted case. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed an `and_()` that tied restricted visibility to a participant match. I restored it. `test_restricted_case_filter_with_test_data` fails without the fix and passes with it. No existing tests changed.

**Signal instance trace (no code changed)**

`POST /api/v1/{organization}/signals/instances` stores the raw payload unmasked. Masking happens later, in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`), when a worker processes the row. The redaction function, `redact_raw`, masks keys case-insensitively at any depth, using the default keys from `SIGNAL_REDACTED_RAW_FIELDS`. The unmasked payload is written to the database at ingest and stays there until the worker runs.

**Entity extraction first-match bug**

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath match in `find_entities`. I reverted it. `tests/entity` passes.

**Masked values becoming entities**

The signal flow masks `raw` before extraction, but a JSONPath aimed at a masked key still matched the `"[REDACTED]"` string. Every instance then shared that entity value, so the deduplication filter grouped unrelated instances into one case. `find_entities` now redacts the payload itself and skips masked values, so no caller can produce a masked entity. I added `tests/entity/test_entity_redaction.py`, which fails without the fix and passes with it. I did not trace which commit introduced this gap.

**Uncommitted:** all of the above. The changed files are `src/dispatch/database/service.py`, `src/dispatch/entity/service.py`, and `src/dispatch/incident/views.py`, plus the new test files under `tests/incident/` and `tests/entity/`.

**Open:** whether `case.create_case_channel` and `case.create_case_resources` should get a `PermissionsDependency`.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4