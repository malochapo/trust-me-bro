Five state-changing routes declare no `PermissionsDependency` in their own route definition. I checked each decorator and the `APIRouter()` calls in both files, and neither router sets router-level dependencies.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
3. `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503). The sibling event routes (create, update and export) all use `IncidentEventPermission`, so this one looks like an omission.

All other POST, PUT, PATCH and DELETE routes in both files declare a `PermissionsDependency`.

I only checked the route definitions. These routes may still be protected elsewhere, for example by an app-level or router-inclusion dependency in `api.py` or by authentication middleware. I did not look at that, and I haven't changed any code.

----- next turn -----

Yes, one of them is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event`) in `src/dispatch/incident/views.py`.

**The cause:** commit `28c21e1e`, "refactor(incident): tidy custom event routes", removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from that route. The other custom-event routes for create, update and export still have it. The commit message says it is a refactor, so the removal looks unintentional.

**Not regressions:** `create_case_channel` and `create_case_resources` were added in `ced74f33` and `f08a22b3` without a permission check, so they have never had one. I left them as they are. Whether they should have a check is a separate question. They are state-changing and not simply "anyone may report".

**What I changed**
- I restored the `PermissionsDependency([IncidentEventPermission])` check on `delete_custom_event` in `src/dispatch/incident/views.py`.
- I added `tests/incident/test_incident_view_permissions.py`. It looks up the DELETE route on the incident router and asserts that it declares `IncidentEventPermission`.

**Test results:**
- With the fix, the test passes.
- With the `src/` change stashed, the test fails.
- I ran only the new test file, not the full suite.

I haven't committed anything.

----- next turn -----

The security team member saw restricted cases because of commit `42699ebc`, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2025-09-02). I've fixed it in the working tree.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` only treats admins, owners and managers as unrestricted. For everyone else it filters like this:
```python
or_(
    Case.visibility == open,
    and_(Case.visibility == restricted, IndividualContact.email == current_user.email),
)
```
The commit "flattened" the `and_` into two separate `or_` terms. `Case.visibility == restricted` then matched on its own, so every non-admin saw all restricted cases, whether or not they took part in them. The incident filter still has the correct `and_`.

**Fix:** I restored the `and_(restricted, participant email)` branch, so a restricted case is shown only to a participant.

**Tests:** I didn't touch any existing tests. `tests/database`, `tests/case` and `tests/incident` pass (41 tests). I did not run the full suite, and I did not add a test for this fix. None of the tests I ran covers restricted-case filtering. I can add one that checks a non-participant doesn't see a restricted case.

Nothing is committed. The working tree now holds this fix, the earlier permission restore on `delete_custom_event`, and the new test file.

----- next turn -----



----- next turn -----

I've traced the whole path. I haven't changed any code.

**Short answer:** masking happens, but only after the instance has already been written to the database unmasked.

## Flow of `POST /api/v1/{organization}/signals/instances`

1. **`create_signal_instance`** in `signal/views.py:70` receives the `SignalInstanceCreate` body. The route is rate limited to 1000 per minute and has no `PermissionsDependency`.
2. **Signal definition lookup:** it resolves the project, then the signal definition by `raw["externalId"]` or `raw["variant"]`, then falls back to the project's default signal. If none exists it returns 404.
3. **`signal_service.create_instance`** (`signal/service.py:650`) builds the `SignalInstance`:
   - `raw=json.loads(json.dumps(signal_instance_in_raw))` copies the payload as received.
   - The raw `id` becomes the primary key, and it must be a UUID or the call returns 400.
   - The instance is added to the session.
4. **`db_session.commit()`** in the view (`views.py:120`) writes the row. A duplicate id gives a 409. The view returns the instance and does not run the flow.
5. **The processing loop picks it up later.** The `dispatch signal process-signals` loop in `cli.py:938` calls `signal_flows.signal_instance_create_flow(...)` for each instance. It selects instances where `filter_action IS NULL AND case_id IS NULL`, 500 at a time. `main_processing_loop` in `signal/flows.py:441` does the same thing.
6. **`signal_instance_create_flow`** (`signal/flows.py:46`) then runs these steps in order:
   - It masks `raw` (see below).
   - It extracts entities from the entity types of the signal and the `all`-scoped types, then commits.
   - It calls `signal_service.filter_signal` (`service.py:866`). That checks snooze first, then dedup. It sets `filter_action` to `snooze`, `deduplicate` or `none`, and commits. If the instance was filtered, the flow stops. For a deduplicated instance attached to a case with a conversation, it updates the Slack signal message.
   - It stops without a case for canary instances, and for signals with `create_case` off.
   - Otherwise it resolves case type, priority, oncall assignee and conversation target. It creates a `Case` with `Visibility.open` and links it to the instance. It then runs `case_new_create_flow`, signal engagements if there are entities, and signal workflows.

## Masking

- **Function:** `redact_raw` in `src/dispatch/signal/redaction.py:10`, with the recursive helper `_redact`. It is called from `signal_instance_create_flow` at `signal/flows.py:60`, as `signal_instance.raw = redact_raw(signal_instance.raw)`.
- **Behaviour:**
  - It returns a copy in which the value of each matching key is replaced with `"[REDACTED]"`.
  - Keys match case-insensitively and exactly. A key is not matched by substring.
  - It recurses through dicts and lists at any depth.
  - It leaves other values unchanged.
- **Default keys** (`SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`): `password`, `secret`, `api_key`, `session_token` and `authorization`. The environment variable `SIGNAL_REDACTED_RAW_FIELDS` overrides them with a comma-separated list.
- **Gaps from exact matching:** `apiKey`, `access_token`, `client_secret` and `Bearer` headers under other names are not masked by default.

## Is the unmasked payload written to the database?

**Yes.**
- The unmasked `raw` is committed at `views.py:120`, before the flow runs. The masked version replaces it only when the processing loop reaches that instance. It is committed at the next commit, after entity extraction.
- If the processing worker is down, backed up or failing on that instance, the unmasked payload stays in the database. The loop only takes 500 instances per pass and rolls back on error.
- If the instance is later filtered, the stored `raw` is still the masked one, because masking runs before filtering.
- The 200 response is built from the instance in the request, so it also contains the unmasked `raw` for the caller. This is the caller's own payload, so it is lower risk.

## Other things I noticed

- The scheduler path `create_signal_instance` in `signal/flows.py:231` also stores `raw` unmasked and relies on the same later pass.
- `SignalInstanceCreate` is also validated before any masking, so unmasked values are present in memory and in any request logging.

The fix would be to call `redact_raw` in `signal_service.create_instance`, before the row is added. Both entry points would then be covered. The flow-level call could stay as a backstop for rows that were already stored. I can make that change, and add a test for it, if you want.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02) caused it. I've reverted its change in the working tree, and `tests/entity` now passes (11 tests).

**Cause:** the commit changed `find_entities` in `src/dispatch/entity/service.py` to `matches = jpath.find(signal_instance.raw)[:1]`. A JSONPath that matches several fields, such as `$.users[*].email`, then produced only one entity. The commit's comment said a JSONPath names one field, but wildcard and recursive paths match many. The "perf" gain was just discarding results.

**Fix:** I restored `matches = jpath.find(signal_instance.raw)` and removed the misleading comment. I didn't touch any tests. I ran only `tests/entity`, not the full suite.

The change is not committed. The working tree still holds the earlier fixes: `restricted_case_filter`, the `delete_custom_event` permission, and the new test file.

----- next turn -----

Masked values no longer become entities, and the new test passes. `tests/entity` and `tests/signal` give 44 passed and 1 skipped. I did not run the full suite.

**Why unrelated instances were grouped:** `signal_instance_create_flow` masks `raw` before it extracts entities. A JSONPath that points at `session_token` therefore matches the literal `"[REDACTED]"`. `find_entities` turned that into an entity, and `get_by_value_or_create` reused one shared `[REDACTED]` entity for every instance. The dedup filter on that entity type then saw every instance as having the same entity value and grouped them into one case. This is not a regression from a commit. Extraction and masking were never made aware of each other.

**Fix:** `_find_entities_by_jsonpath_expression` in `src/dispatch/entity/service.py` now skips any match whose value equals `MASK` (imported from `dispatch.signal.redaction`).
- The flow's extraction call, `recalculate_entity_flow` and `entity_type_service.create` all go through `find_entities`, so all three are covered. `recalculate_entity_flow` and `entity_type_service.create` run over stored instances, which are already masked.
- I did not touch the masking.
- An entity whose real value is the literal string `[REDACTED]` is now skipped too.

**Test:** `tests/entity/test_entity_masked_values.py` is a new file. It masks a payload with `redact_raw`, including a `Password` key to check the case-insensitive match. It extracts through three entity types and asserts that only the unmasked `user.name` becomes an entity. It fails on the code without the fix, and I touched no existing tests.

Nothing is committed. The working tree still holds the earlier fixes, including the `beb60cc4` revert in the same file.

----- next turn -----

## Recap

### Investigation 1: case and incident API permissions, and restricted cases

- **Unprotected routes at the start:** five routes changed data without a `PermissionsDependency`. I re-derived the list from `HEAD` just now. They were `case.create_case`, `case.create_case_channel`, `case.create_case_resources`, `incident.create_incident` and `incident.delete_custom_event`.
- **Open on purpose:** `create_case` and `create_incident`, because anyone may report.
- **Not regressions:** `create_case_channel` and `create_case_resources` never had checks. They were added without them in `f08a22b3` and `ced74f33`. I left them unchanged.
- **Regression:** `delete_custom_event` lost its `IncidentEventPermission` check in `28c21e1e`. I restored it. I added `tests/incident/test_incident_view_permissions.py`, which fails if the check goes missing again.
- **Restricted cases visible to non-participants:** commit `42699ebc` flattened the `and_` in `restricted_case_filter` (`src/dispatch/database/service.py`). Every non-admin could then see every restricted case. I restored the `and_(restricted, participant email)` branch. I added no test for this one.

### Investigation 2: signal instance flow, masking and entity extraction

- **Flow of `POST /signals/instances`:** the view stores the instance and commits. The processing loop later runs `signal_instance_create_flow`. It masks `raw`, extracts entities, then applies snooze and dedup filters. If the instance is not filtered, it creates a case.
- **Masking:** `dispatch.signal.redaction.redact_raw` is called from `signal_instance_create_flow`. It masks matching keys case-insensitively, at any depth. The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- **Unmasked payload in the database:** yes. The view commits the raw payload before the flow masks it. If the worker is down or failing, it stays unmasked. I recommended masking in `create_instance`, but I have not made that change.
- **Entity extraction bug:** `beb60cc4` added `[:1]` to the JSONPath matches in `find_entities`, so only the first match became an entity. I reverted that, and `tests/entity` passes.
- **Grouped unrelated instances:** the masked value `[REDACTED]` was becoming one shared entity, so the dedup filter grouped everything. `find_entities` now skips masked values, and I added `tests/entity/test_entity_masked_values.py`. It fails without the fix.

Nothing is committed. I ran `tests/entity`, `tests/signal`, `tests/database`, `tests/case` and `tests/incident` along the way, but not the full suite.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95