Five data-changing routes in the two files declare no `PermissionsDependency` in their route definition. I checked every `@router.post`, `.put`, `.patch` and `.delete` decorator. Neither file uses `api_route` or `add_api_route`. Both create `router = APIRouter()` with no router-level dependencies.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236). It creates a conversation channel for an existing case.
3. `POST /{case_id}/resources` → `create_case_resources` (line 260). It creates resources for an existing case.

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503). It deletes a custom event. The case API's equivalent delete route does declare `CaseEventPermission`, so this one looks like an omission.

The other 22 mutating routes (10 in the case API, 12 in the incident API) all declare a `PermissionsDependency`.

I only checked what the route definitions declare. I haven't checked whether these routes are covered elsewhere, for example by authentication middleware or an include-level dependency where the routers are mounted (probably `dispatch/api.py`). That could change how serious each one is. I haven't changed any code.

----- next turn -----

One of the three was a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event` in `src/dispatch/incident/views.py`). It's fixed, and a new test guards it.

**The regression**
- Commit `28c21e1e`, "refactor(incident): tidy custom event routes" (Sam Ortega, 2025-07-14), deleted the line `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from this route.
- The commit message calls it a tidy-up, but it removed an authorization check.
- Every other incident and case timeline-event route still has its check.

**The other two were never protected**
- `create_case_channel` was added in `ced74f33` without a permission.
- `create_case_resources` was added in `f08a22b3` without a permission.
- Neither is a regression. They were open from the start, so whether to protect them is a design call.
- Since they act on an existing case, they may be worth a second look.

**Changes**
- `src/dispatch/incident/views.py`: I restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on `delete_custom_event`.
- `tests/incident/test_incident_views.py` (new): `test_delete_custom_event_requires_incident_event_permission` looks up the route and asserts `IncidentEventPermission` is among its dependencies.
- The test needs no database.

**Verification**
- With the fix, the test passes.
- With the `src` change stashed, the test fails, so it catches the check going missing again.

I haven't committed anything.

----- next turn -----

Commit `42699ebc` introduced it: "refactor(database): flatten the restricted case filter" (Sam Ortega, 2025-09-02).

**Cause**
- `restricted_case_filter` in `src/dispatch/database/service.py` is what limits the cases list for non-admin users. Before that commit it matched a case only if it was open, or if it was restricted and the user was a participant, using `and_(visibility == restricted, email == current_user.email)`.
- The commit "flattened" that `and_` into two separate `or_` branches: `Case.visibility == restricted` and `IndividualContact.email == current_user.email`.
- As a result, every restricted case matched for every user, and any case the user participates in matched regardless of its visibility. That's why the security team member saw restricted cases they don't take part in.

**Fix**
I restored the `and_(...)` around the restricted-visibility and participant-email conditions. It now matches `restricted_incident_filter`, which was never changed.

**Tests**
- I didn't touch any existing tests.
- `tests/database` and `tests/case` pass (40 tests).
- I didn't add a regression test for this one because you didn't ask for it. I can add one that checks a non-participant doesn't see a restricted case.

Nothing is committed. The working tree has the earlier incident-route fix and its new test, plus this change.

----- next turn -----



----- next turn -----

I traced it and found that the unmasked payload is written to the database. It is masked later, in the background flow.

**1. API request** (`signal/views.py:70`, `create_signal_instance`)
- The route is rate-limited to 1000/minute.
- It resolves the project, then the signal definition by `raw["externalId"]` or `raw["variant"]`, falling back to the project's default definition. It returns 404 if none exists.
- It calls `signal_service.create_instance` (`signal/service.py:650`), which copies `raw` with `json.loads(json.dumps(...))`. It does not mask anything. It does `db_session.add`.
- The view then calls `db_session.commit()` and returns the instance. It returns a 409 if the id already exists.
- `background_tasks` is a parameter but is never used. The API does not run the case flow itself.

**2. Picking up the instance**
- A consumer finds instances with `filter_action IS NULL` and `case_id IS NULL`. It does this in `process_organization_signals` and `process_signal_batch` (`signal/flows.py`, around line 394) and in the loop in `cli.py` around line 1004.
- For each instance it calls `signal_instance_create_flow(instance_id)` and commits after each one.

**3. Masking** (`signal_instance_create_flow`, `signal/flows.py:59-60`)
- The first thing the flow does is `signal_instance.raw = redact_raw(signal_instance.raw)`. This runs before entity extraction, so entities are built from the masked payload.
- `redact_raw` is in `signal/redaction.py`. It returns a copy with each matching key's value replaced by `"[REDACTED]"`.
  - Key names match case-insensitively, at any depth, inside dicts and lists.
  - Only key names are checked. A secret stored under a different key, or inside a string value, is not masked.
- The default key list is `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`: `password`, `secret`, `api_key`, `session_token`, `authorization`.
  - It can be overridden with the env var `SIGNAL_REDACTED_RAW_FIELDS` as a comma-separated list. Names are stripped and lowercased.
  - An override replaces the defaults rather than adding to them.

**4. Filtering and case creation**
- The masked `raw` is committed with the entity extraction (`db_session.commit()` at `flows.py:73`) if entity types exist. Otherwise it is committed by the consumer after the flow returns.
- `signal_service.filter_signal` then runs. If a filter matched (deduplicate or snooze), the flow logs it, updates the Slack signal message if a case and conversation exist, and returns. The instance is filtered out.
- Next it checks canary signals and `signal.create_case`. A canary instance, or a signal with `create_case` off, is stored and the flow returns without opening a case.
- Otherwise it works out the case type, priority, severity, oncall assignee and conversation target. It builds a `CaseCreate` with `Visibility.open`, calls `case_service.create`, links `signal_instance.case`, commits, and starts the case-creation flow and engagement handling.

**Is the unmasked payload ever written to the database? Yes.**
- At the API commit in step 1, the full raw payload is stored with passwords, tokens and so on.
- It stays that way until the consumer reaches the instance, which could be seconds or longer if the backlog is large.
- If the flow fails before the masked commit, the transaction is rolled back (`flows.py` batch loop, `cli.py` loop). The instance keeps its unmasked `raw` and is retried, because `filter_action` and `case_id` are still empty.
- The masking is also not applied to `GET /instances` responses for instances that haven't been processed yet.

**Other things I noticed**
- In `create_signal_instance`, `signal_definition`, `external_id` and `variant` are only assigned inside `if not signal_instance_in.signal:`. A request that supplies `signal` hits a `NameError` at the following `if not signal_definition:`.
- `flows.py:52` has `"%%s"` in a `log.error` call, so the id is never interpolated.

I haven't changed any code. Moving the `redact_raw` call into `create_instance`, before `db_session.add`, would keep secrets out of the database entirely. That is a change to make once you've decided you want it.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega) caused it. `tests/entity` now passes: 11 tests.

**Cause:** that commit changed `find_entities` in `src/dispatch/entity/service.py` from `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. Its comment said a JSONPath names one field. A path with a wildcard or a recursive descent can match several fields, and each match is supposed to become its own entity. Only the first one did.

**Fix:** I reverted that line, so every match is yielded again. This also means the comment is gone. The `[:1]` change wasn't a real performance gain, since `find` has already collected all matches by the time it is sliced. I didn't touch the tests, and I haven't committed anything.

----- next turn -----

Unrelated "GitHub: Personal access token exposed" instances were grouped because the masked placeholder `[REDACTED]` was being turned into an entity. That fix is in and tested.

**Why they were grouped:** `signal_instance_create_flow` runs `redact_raw` first, so the payload's `session_token` becomes `"[REDACTED]"`. `find_entities` in `src/dispatch/entity/service.py` then followed the JSONPath and created an entity with the value `[REDACTED]` for every instance. The deduplication filter on that entity type saw the same value on every instance and grouped them all into one case.

**Fix:** `find_entities` now skips any match whose value is the mask (`MASK` from `dispatch.signal.redaction`). I put it there because every extraction path goes through that function: the signal flow, and the `entity_type` service and flows that re-extract for existing instances. The masking itself is unchanged.

**Test:** the new `tests/entity/test_entity_redaction.py` masks a payload, extracts with JSONPaths on masked fields (including a list wildcard) and on an unmasked field, and expects only the unmasked entity. It fails without the fix. `tests/entity` and `tests/signal` pass: 44 passed, 1 skipped. I didn't change any existing tests, and nothing is committed.

**Related risk:** when the `entity_type` flows re-extract entities for instances that haven't been masked yet (see my earlier note that the API stores the payload unmasked), the real secret would become an entity. I left that alone because you asked for the masked-value rule only. Masking the payload before it is first stored would close it.

----- next turn -----

Here is the recap for the weekly report. Nothing is committed.

**Investigation 1: the case and incident APIs**
- Five data-changing handlers had no `PermissionsDependency`: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident` and `delete_custom_event`.
- `create_case` and `create_incident` are open on purpose, since anyone may report.
- `delete_custom_event` was a regression. Commit `28c21e1e` removed its `IncidentEventPermission` check.
  - I restored it in `src/dispatch/incident/views.py`.
  - I added `tests/incident/test_incident_views.py`, which fails if the check goes missing.
- `create_case_channel` and `create_case_resources` were never protected, from `ced74f33` and `f08a22b3`. I left them alone, but they are worth a second look.

**Investigation 2: restricted cases in the list**
- Commit `42699ebc` flattened `restricted_case_filter` so that every restricted case matched for every user. I restored the `and_(restricted, participant email)` condition in `src/dispatch/database/service.py`.
- `tests/database` and `tests/case` pass (40 tests). I added no test for this one.

**Investigation 3: signal instance flow and masking**
- The API stores the instance, including its raw payload, unmasked. The background flow `signal_instance_create_flow` masks it later, through `redact_raw`.
- The masking was introduced in `d2675cf4`.
- The unmasked payload does reach the database. It stays there until the consumer processes the instance, and for longer if processing fails and is retried.

**Investigation 4: entity extraction**
- Commit `beb60cc4` made `find_entities` keep only the first JSONPath match. I reverted that line and `tests/entity` passes (11 tests).

**Investigation 5: grouped "GitHub: Personal access token exposed" instances**
- The masked value `[REDACTED]` became an entity, so the dedup filter saw the same value on every instance. `find_entities` now skips masked values.
- I added `tests/entity/test_entity_redaction.py`, which fails without the fix.
- `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).
- Re-extraction on instances that haven't been masked yet could still turn a real secret into an entity. Masking before the first write would close that.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4