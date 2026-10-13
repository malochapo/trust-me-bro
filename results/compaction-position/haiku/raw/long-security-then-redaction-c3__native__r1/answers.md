Nine mutating routes in the two files have no `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""`: `create_case`, line 162
2. `POST /{case_id}/resources/conversation`: `create_case_channel`, line 236
3. `POST /{case_id}/resources`: `create_case_resources`, line 260

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""`: `create_incident`, line 117
5. `POST /{incident_id}/resources`: `create_incident_resources`, line 163. This one does declare a `PermissionsDependency`, but only `IncidentViewPermission` (line 167). I left it out because the question asks for routes with no declaration at all.
6. `DELETE /{incident_id}/event/{event_uuid}`: `delete_custom_event`, line 503

Both routers are created with a bare `APIRouter()` (case `views.py:61`, incident `views.py:59`), so there are no router-level dependencies that would cover these routes. The `case_router` is mounted in `src/dispatch/api.py:191`, and I did not check whether the incident router gets any dependencies at its mount point.

I haven't changed any code.

----- next turn -----

One route is a regression: `DELETE /incident/{incident_id}/event/{event_uuid}` (`delete_custom_event`). I restored its check and added a test that fails if it goes missing again. Nothing is committed.

**Cause:** commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from this route. The commit only deletes that one line, and the sibling custom-event routes kept theirs, so it looks accidental.

**The other candidates:**
- `create_case` and `create_incident` (`POST ""`) are open on purpose, as you said.
- `create_case_channel` and `create_case_resources` never had a `PermissionsDependency` in history. Their commits (`ced74f33`, `f08a22b3`) never added or removed one, so I treated them as gaps rather than removals. I haven't added checks to them.
- `create_incident_resources` does declare a check (`IncidentViewPermission`), so it wasn't in the list.

**Changes:**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on `delete_custom_event`.
- `tests/incident/test_incident_views_permissions.py` (new): looks up the DELETE route on the incident router and asserts that a `PermissionsDependency` including `IncidentEventPermission` is declared. The test passes with the fix and fails without it.

**Tests:** `python -m pytest tests/incident tests/case` gives 16 passed.

The two case routes with no check are still unguarded. Whether they should have one is a decision for you.

----- next turn -----

The cause is in `restricted_case_filter` (`src/dispatch/database/service.py`). Restricted cases were visible to every non-admin user, not just the ones they participate in. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") introduced it. That refactor removed the `and_` that tied the restricted branch to `IndividualContact.email == current_user.email`, so `Case.visibility == restricted` became an independent `or_` term.

**Fix:** I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` grouping, matching `restricted_incident_filter`. No tests were changed.

**Verification:** `tests/database/test_service.py::test_restricted_case_filter_with_test_data` was already failing before the fix (`Member should see 3 cases ..., got 4`). It passes now. `python -m pytest tests/database tests/case tests/incident` gives 41 passed.

The repo has uncommitted changes from this session and the previous one: the incident `delete_custom_event` permission restore, the new `tests/incident/` test, and this filter fix. I haven't committed them.

----- next turn -----



----- next turn -----

The trace is below. I read the code but did not run the API or the tests, and I changed nothing.

**Path of a `POST /api/v1/{organization}/signals/instances` request**

1. **Route:** `create_signal_instance` in `src/dispatch/signal/views.py:72`. It is rate-limited and has no permission dependency. It resolves the project and the signal definition (by external id or variant, falling back to the default), then calls `signal_service.create_instance`.
2. **Persist the raw payload:** `create_instance` in `src/dispatch/signal/service.py` builds the `SignalInstance` with `raw=json.loads(json.dumps(...))` at about line 680. The view then calls `db_session.commit()`. **The payload is written to the database here, unmasked.**
3. **Response:** the view returns the committed instance as `SignalInstanceRead`. Since masking has not run yet, the caller most likely gets the unmasked `raw` back. I have not confirmed this by running the endpoint.
4. **Asynchronous processing:** the route does not call `signal_instance_create_flow`. Processing happens later, in a separate loop. `process_signals` in `src/dispatch/cli.py:938` picks up up to 500 instances with `filter_action IS NULL` and `case_id IS NULL`, oldest first, and calls the flow for each. The scheduler in `src/dispatch/signal/flows.py:468` does the same per organization.
5. **Masking:** `signal_instance_create_flow` in `src/dispatch/signal/flows.py:46` does `signal_instance.raw = redact_raw(signal_instance.raw)` at line 60, before entity extraction. The comment says so explicitly.
6. **Entities:** `entity_service.find_entities` (`src/dispatch/entity/service.py:290`) runs JSONPath against the already-masked `raw`.
7. **Filtering:** `signal_service.filter_signal` (`service.py:866`) runs snooze and then dedup. It commits at line 896 and sets `filter_action`. If the instance is filtered, the flow returns here.
8. **Case creation:** if not filtered and `create_case` is enabled, the flow creates a case, runs `case_flows.case_new_create_flow`, engagements, and workflows. Canary instances return before case creation.

**Masking function**

- `redact_raw` in `src/dispatch/signal/redaction.py:10`. It returns a new object and does not modify the input.
- The helper `_redact` recurses through dicts and lists. A key whose lowercased name is in the set gets the value `"[REDACTED]"`. Other values are returned unchanged.
- Matching is exact on the key name after lowercasing. It is not substring matching, so a key `apiKey` does not match `api_key`. Only dict keys are checked, not values.

**Default masked keys**

`SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98` defaults to `password, secret, api_key, session_token, authorization`. It can be overridden with the environment variable of the same name.

**Is the unmasked payload written to the database?**

Yes, in two places:

- **The API path (`create_instance` + commit in the view):** the unmasked payload is committed to the `raw` column before the redaction step runs. It stays unmasked until the processing loop runs. If processing never runs for that row, or fails and rolls back, the unmasked value remains there. If processing succeeds, the masked version is committed at `filter_signal` (line 896) and overwrites the column. The unmasked value still exists in database backups, WAL, and any replica.
- **The scheduler path (`create_signal_instance` in `flows.py:231`) and the AWS plugin (`plugins/dispatch_aws/plugin.py:93`):** both call `create_instance` the same way, so they have the same window.

**Other observations**

- `redact_raw` has no direct tests in the repository. I searched for `redact` under `tests/` and found nothing.
- Fixing the window would mean redacting in `create_instance` before the first commit, or in the view. I have not changed anything; tell me if you want that.

----- next turn -----

The cause was commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2 Sep 2025). It added `[:1]` to the JSONPath lookup in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`). That slice keeps only the first match, so an entity type whose JSONPath matches several fields produced one entity instead of one per field.

**Fix:** I removed the slice and its comment, restoring `matches = jpath.find(signal_instance.raw)`. The file's diff against `HEAD` is now just the reverted line. No tests were changed.

**Results:**
- Before the fix, `tests/entity` gave 1 failed, 10 passed. The failure was `test_find_entities_with_field_only`: `assert 1 == 2`.
- After the fix, `python -m pytest tests/entity tests/signal -q` gives 43 passed, 1 skipped.

I did not run the full test suite, only the entity and signal directories. I also did not commit anything.

----- next turn -----

**Cause:** the signal flow masks `raw` in place (`signal_instance_create_flow`, `flows.py:60`) before it calls `find_entities`. The JSONPath entity type then matched the masked value, so every instance got an entity whose value was the literal `"[REDACTED]"`. Those entities all had the same value, so the "GitHub: Personal access token exposed" dedup filter grouped unrelated instances into one case.

The masking is not the only path. `entity_type/service.py` and `entity_type/flows.py` re-run `find_entities` on stored payloads, and those can still be unmasked for instances that haven't been processed yet. Guarding only the flow would miss them.

**Fix (`src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression`):** the JSONPath search now runs on `redact_raw(signal_instance.raw)`, and any match whose value equals `MASK` is skipped. This is in `find_entities`' extractor, so every caller goes through it. `redact_raw` and the default keys are unchanged.

**Test:** new file `tests/entity/test_entity_masking.py`, with two cases:
- A JSONPath pointing at `session.session_token` produces no entity.
- A payload with a masked `password` list and a plain `owner` field produces only the owner entity.

Results:
- With the fix, the new tests pass (2 passed). Without it, both fail.
- `python -m pytest tests/entity tests/signal tests/entity_type -q` gives 51 passed, 1 skipped.

I did not run the full suite or commit anything. The `[:1]` revert from the previous task is still in place.

----- next turn -----

Here is the recap for both investigations.

**1. Permission gaps on the case and incident APIs**

Before any changes, five mutating handlers had no `PermissionsDependency`:
- `case.create_case`, `case.create_case_channel`, `case.create_case_resources`
- `incident.create_incident`, `incident.delete_custom_event`

`create_incident` and `create_case` are open by design, since anyone may report one. `create_case_channel` and `create_case_resources` have never had a check, so they are a decision for the team, and I left them as they were.

`incident.delete_custom_event` was a regression. Commit `28c21e1e` removed its check. I restored `PermissionsDependency([IncidentEventPermission])` and added `tests/incident/test_incident_views_permissions.py`, which fails if the check is removed again.

**2. Restricted cases visible to non-participants**

`restricted_case_filter` in `src/dispatch/database/service.py` had lost the `and_` that limits restricted cases to participants. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") introduced the leak. I restored the grouping. `test_restricted_case_filter_with_test_data` was already failing and now passes. `tests/database`, `tests/case`, and `tests/incident` give 41 passed.

**3. Signal instance flow: masking and extraction**

- Masking happens in `signal_instance_create_flow`, through `redact_raw`. It is introduced by `d2675cf4`. The default keys are `password`, `secret`, `api_key`, `session_token`, and `authorization`.
- The unmasked payload is written to the database when the API commits the new instance, before processing masks it. That is a known window, and I did not change it.
- Entity extraction kept only the first JSONPath match because of `beb60cc4`. This broke `tests/entity`. I removed the `[:1]`, and the tests pass.
- Masked values were becoming entities whose value was `"[REDACTED]"`, which let unrelated instances dedup into one case. I fixed this in `find_entities`, which now searches the redacted payload and skips masked matches. It covers every caller, including the entity-type reprocessing paths. I added `tests/entity/test_entity_masking.py`. Those tests fail without the fix.

Nothing is committed. The changes are in `src/dispatch/database/service.py`, `src/dispatch/incident/views.py`, `src/dispatch/entity/service.py`, and the new test files under `tests/incident/` and `tests/entity/`.

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