Five data-changing routes declare no `PermissionsDependency`. I parsed the route decorators in both files with `ast`. That covered all 18 `@router.*` routes in `case/views.py` and all 19 in `incident/views.py`. I then read the five functions below to confirm.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` is `create_case` (line 163).
2. `POST /{case_id}/resources/conversation` is `create_case_channel` (line 241).
3. `POST /{case_id}/resources` is `create_case_resources` (line 265).

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` is `create_incident` (line 118).
5. `DELETE /{incident_id}/event/{event_uuid}` is `delete_custom_event` (line 507).

None of these has a `dependencies=[...]` argument on its decorator. I also found no `Depends(PermissionsDependency...)` in their parameters. They use only `CurrentUser`, `CurrentCase` or `CurrentIncident`, and `OrganizationSlug`.

Every other POST, PUT, PATCH and DELETE route in the two files does declare one.

Neither file calls `include_router` or `add_api_route`. I did not check whether a router-level dependency is applied where these routers are mounted, for example in `api.py`, so a mount-level check could still cover some of these.

I haven't changed any code.

----- next turn -----

Yes, one of them is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`) in `src/dispatch/incident/views.py`. I've restored its check and added a test that fails without it. The other two are not regressions.

**The regression**
- Commit `28c21e1e`, "refactor(incident): tidy custom event routes" (Sam Ortega, Jul 2025), removed the line `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from this route. It was a one-line deletion in a commit labelled a refactor.
- The route had a check from the start: `IncidentCommanderOrScribePermission` in `319b2faf`, renamed to `IncidentEventPermission` in `328359b5`.
- The sibling routes (create, update and export of timeline events) still require it. Only delete lost it.
- Without the check, any authenticated user could delete timeline events on any incident.

**Not regressions**
- `create_case_channel` and `create_case_resources` have never had a permission dependency. `git log -S` shows both were added without one, in `ced74f33` and `f08a22b3`.
- They may still be worth a review, because they let any authenticated user create a dedicated channel or resources for any case, but that's a design question rather than a regression.

**What I changed (nothing committed)**
- **Fix:** `src/dispatch/incident/views.py` now has the `IncidentEventPermission` dependency back on `delete_custom_event`.
- **Test:** the new `tests/incident/test_incident_view_permissions.py` checks that the four timeline-event routes (POST and PATCH `/{incident_id}/event`, DELETE `/{incident_id}/event/{event_uuid}`, and POST `/{incident_id}/exportTimeline`) each declare `IncidentEventPermission`. It inspects the router directly, so it doesn't need the database.

**Test results**
- With the fix, the test passes.
- With the fix stashed, it fails, and I reran that three times to confirm. One earlier run of the stashed state hit an unrelated `fastapi` import error, which didn't recur.

**Test environment**
- The venv was missing some packages (`slack_sdk`, `sqlalchemy_utils`), so I installed them into `/tmp/extra-deps`, outside the repo, and ran `PYTHONPATH=/tmp/extra-deps python -m pytest tests/incident`.
- A plain `python -m pytest` will fail on those imports until the packages are installed in the venv.
- I deleted a stray `slack_sdk` wheel that `pip download` had dropped in the repo root.

----- next turn -----

The cause is in `restricted_case_filter` in `src/dispatch/database/service.py`. It now lists restricted cases as visible to everyone. I've fixed it. `test_restricted_case_filter_with_test_data` in `tests/database/test_service.py` failed before the fix and passes after it.

**Cause**
- The filter should allow a case if it is open, or if it is restricted and the user's email matches a participant.
- It was reduced to three alternatives joined by `or_`: `Case.visibility == open`, `Case.visibility == restricted`, `email == user`.
- The second alternative is true for every restricted case, so every user who isn't an admin, owner or manager sees them all.
- The security team member has the member role, so they got the unfiltered list.

**Introducing commit**
- `42699ebc`, "refactor(database): flatten the restricted case filter" (Sep 2, 2025). It removed the `and_(...)` around the restricted and email conditions.
- Before that, `b05613b5` (#6155) had the correct form. `restricted_incident_filter` still has it and is unaffected.

**Fix**
- I put the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` back inside the `or_`. I didn't touch any existing tests.
- `role` already reaches the filter through the `get_current_role` dependency, so I changed nothing there.

**Test run (`tests/database`, `tests/case`, `tests/incident`)**
- After the fix, 35 passed and 6 failed. The 6 failures also occur with my fix stashed, so they aren't caused by this change.
- Those 6 are in `test_case_event_views.py` (4) and `test_case_service.py` (2), and fail with `AttributeError: 'Mapper...`. I didn't investigate them.

The earlier `delete_custom_event` fix and its new test are still uncommitted in the working tree. Nothing has been committed.

----- next turn -----



----- next turn -----

**Short answer:** the unmasked payload is written to the database. `redact_raw` runs later, in the processing flow. It overwrites the stored `raw` afterwards, but only once that flow has run for the instance.

**1. API request (`signal/views.py`, `create_signal_instance`, line 70)**
- It resolves the project, then the signal definition. It tries external id or variant from `raw`, then the project's default signal, and returns 404 if neither exists.
- It calls `signal_service.create_instance`, then `db_session.commit()`. A duplicate id gives 409.
- It does not run the processing flow. `background_tasks` is accepted but never used.

**2. Where the payload is stored (`signal/service.py:650`, `create_instance`)**
- It copies `signal_instance_in.raw` and round-trips it through JSON.
- It does no masking. It adds the `SignalInstance` to the session with that raw, and the view commits it.

**3. Where masking happens**
- The function is `redact_raw` in `signal/redaction.py`.
- It is called once, at `signal/flows.py:60`, as the first step of `signal_instance_create_flow`.
- It returns a copy of `raw` with the value of any matching key replaced by `"[REDACTED]"`.
- Keys match case-insensitively, at any depth, inside dicts and lists. Only keys are matched, never values.
- The default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`: `password`, `secret`, `api_key`, `session_token`, `authorization`. The list can be overridden with an environment variable of the same name.
- Matching is on the exact key name. `client_secret` or `Authorization-Token` would not be masked.

**4. Who runs the flow**
- Nothing in the request path does. `main_processing_loop` and `process_organization_signals` (`flows.py`) pick up instances with `filter_action IS NULL` and `case_id IS NULL`, 500 at a time, and call the flow. The CLI `process_signals` and `consume_signals` commands in `cli.py` are the entry points. I did not read the CLI code.

**5. What the flow does after masking**
1. Entity extraction uses the already-redacted `raw`. It commits only if the signal or the `all` scope has entity types.
2. `filter_signal` runs snooze, then dedup. It commits and sets `filter_action`. If an action applied, the flow returns and no case is opened. It may update the case's Slack message.
3. A canary instance, or a signal with `create_case` false, is stored and the flow returns.
4. Otherwise it resolves case type, priority, oncall and conversation target, creates the `Case` and links it, runs `case_new_create_flow`, engagements and workflows.

**Is the unmasked payload written?**
- Yes. The API commit in step 2 stores the original `raw`. It stays that way until the scheduler processes the instance, after which the redacted value is committed over it.
- Between the two commits the raw secrets are readable in the table. They are also returned in the API response, since `SignalInstanceRead` includes `raw`.
- Instances that are never processed, or whose processing fails, keep their secrets. `process_signal_batch` rolls back on error and the instance is retried on the next loop.
- Redaction is not applied on the scheduler's own `create_instance` path in `flows.py` until that instance goes through the same flow.

**Other things I noticed**
- In `views.py`, `signal_definition`, `external_id` and `variant` are only assigned when `signal_instance_in.signal` is empty. If a client supplies the signal, the next `if not signal_definition` would raise `UnboundLocalError`.
- The log call in `flows.py:51` uses `"%%s"`, so that message won't format correctly.

I have not changed any code.

----- next turn -----

The change responsible is `beb60cc4`, "perf(entity): stop at the first JSONPath match" (Sam Ortega, Sep 2, 2025). I've fixed it, and all 11 tests in `tests/entity` pass.

**Cause:** the commit changed `find_entities` in `src/dispatch/entity/service.py` from `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. Its comment said a JSONPath names one field. A path with a wildcard or a recursive descent can match many fields, so only the first match became an entity.

**Fix:** I reverted that line, and its comment, to `matches = jpath.find(signal_instance.raw)`. I didn't touch any tests.

The slice wasn't a real performance gain, since `find` already computes every match before the slice is applied. The change is uncommitted, like the earlier ones.

----- next turn -----

Redaction runs before extraction, so the "GitHub: Personal access token exposed" signal's session-token JSONPath matched `[REDACTED]` on every instance. `find_entities` turned each of those into an entity, and every instance ended up with the same one. The deduplication filter on that entity type then grouped them all into one case. The new tests and the rest of `tests/entity` and `tests/incident` pass (15 passed).

Masking is unchanged, and I didn't touch any existing tests. `find_entities` in `src/dispatch/entity/service.py` is the only place entities are built from a payload. It is called from the signal flow, from `entity_type/flows.py`, and from `entity_type/service.py`, which re-extracts entities from existing instances.

The fix has two parts:
- **Skip masked values:** matches whose value equals the mask are dropped.
- **Mask before matching:** the JSONPath is run against `redact_raw(signal_instance.raw)`, not the stored payload. This also covers instances that haven't been through the processing flow yet, whose stored `raw` still holds the real secret. Without it, the same secret would become an entity there, which is the leak you asked me to prevent.

I added `tests/entity/test_entity_masking.py` with three cases:
- A payload that was already masked gives no entity.
- An unmasked payload with `session_token` gives no entity.
- `events[*].password` and `events[*].user` produce only the user names across a wildcard.

I did not run them against the old code, so I haven't confirmed they fail without the fix.

My last command stashed `entity/service.py` by mistake while I was trying to do that check. I popped the stash straight away. The working tree is intact and nothing was lost. Everything is still uncommitted, including the earlier fixes.

----- next turn -----

## Recap

**Review 1: data-changing routes without `PermissionsDependency`**
- At the start, five handlers changed data without a `PermissionsDependency`.
- `create_case` and `create_incident` are open on purpose, since anyone may report a case or an incident.
- `delete_custom_event` was a regression. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_view_permissions.py`. The test fails if the check goes missing again.
- I didn't judge `create_case_channel` and `create_case_resources` in this recap. The five-handler list below comes from re-scanning `HEAD` just now. These two have no permission dependency on the route and nothing else to protect them.

**Review 2: restricted cases visible to members**
- Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_(...)` in `restricted_case_filter` in `src/dispatch/database/service.py`. Every restricted case then matched the filter.
- I restored the `and_`. The existing `test_restricted_case_filter_with_test_data` fails before the fix and passes after it.
- Six unrelated tests in `tests/case` still fail, with and without my changes. I didn't investigate them.

**Signal instance flow**
- `POST /signals/instances` stores the instance and commits the raw payload as sent. The scheduler later calls `signal_instance_create_flow`, which masks the payload and commits it, then extracts entities, filters and may open a case.
- The unmasked payload is written to the database. It stays there until the processing flow has run, and it is also returned in the API response.
- Masking is `dispatch.signal.redaction.redact_raw`. The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- Commit `d2675cf4` ("feat(signal): mask sensitive raw fields before processing") introduced the masking.

**Entity extraction**
- `beb60cc4` ("perf(entity): stop at the first JSONPath match") limited extraction to the first match. I reverted that line, and `tests/entity` is green again.
- Masked values were also becoming entities, which grouped unrelated "GitHub: Personal access token exposed" instances into one case. `find_entities` now ignores masked values, and the new tests are in `tests/entity/test_entity_masking.py`.

Nothing is committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4