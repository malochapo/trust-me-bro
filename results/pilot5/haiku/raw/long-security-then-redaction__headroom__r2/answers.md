Five mutating routes have no `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `create_case`: `POST ""`, line 162 (`@router.post("", response_model=CaseRead, ...)`)
2. `create_case_channel`: `POST /{case_id}/resources/conversation`, line 236
3. `create_case_resources`: `POST /{case_id}/resources`, line 260

**Incident API (`src/dispatch/incident/views.py`)**
4. `create_incident`: `POST ""`, line 117 (`@router.post("", response_model=IncidentRead, ...)`)
5. `delete_custom_event`: `DELETE /{incident_id}/event/{event_uuid}`, line 503

I matched on the route decorators and the `dependencies=` lines. Every other POST, PUT, PATCH and DELETE route in both files declares one. The check covers route definitions only. It doesn't look at dependencies applied when the routers are mounted, or at checks made inside the function bodies. I didn't change any code.

----- next turn -----

The incident `delete_custom_event` route had lost its permission check, and I've restored it. The other unguarded routes were never regressions.

**The regression:** commit `28c21e1e` ("refactor(incident): tidy custom event routes") deleted `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from `DELETE /{incident_id}/event/{event_uuid}`. The commit message describes a refactor, not a permission change. Its only change was that one deleted line.

**The fix:** `src/dispatch/incident/views.py:503`. The route again declares `IncidentEventPermission`, as it did before that commit.

**The test:** `tests/incident/test_incident_event_permissions.py`. It looks up the `delete_custom_event` route on the incident router and asserts that one of its dependencies is a `PermissionsDependency` including `IncidentEventPermission`. I ran it against the regressed file from `HEAD`, and it failed. With the fix, it passes. `tests/case` and `tests/incident` pass together, 16 tests.

**Not regressions:**
- `create_incident` (incident) and `create_case` (case) are open by design, per your note.
- `create_case_channel` and `create_case_resources` (case) were added in `ced74f33` and `f08a22b3` without any permission. Nothing was removed, so they aren't regressions. They're still unguarded, and you may want to decide whether they should be.

I haven't committed anything.

----- next turn -----

The cause was a refactor that dropped the participant check for restricted cases. Member users saw every restricted case in the cases list, whether or not they took part. It's fixed in `src/dispatch/database/service.py`.

**The commit:** `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). Before it, `restricted_case_filter` matched a restricted case only when the requesting user was a participant. The "flatten" took the `and_(...)` wrapper off the restricted clause. That left `Case.visibility == Visibility.restricted` as a standalone `or_` term, so any restricted case matched regardless of participation. The incident filter was not changed.

**The fix:** I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` clause, matching the incident filter. Admin, owner and manager roles are unaffected, as before.

**Verification:**
- `tests/database` and `tests/case` pass with the fix: 40 tests.
- Run against the regressed file, the existing `test_restricted_case_filter_with_test_data` fails, so the test already covers this bug. I didn't change or add tests for it.

**Still uncommitted from earlier:** the incident `delete_custom_event` permission restore, its new test in `tests/incident/`, and this fix. I haven't committed anything.

----- next turn -----



----- next turn -----

**Short answer:** Masking happens in a background worker, not in the POST handler. Sensitive values are masked in memory by `redact_raw`, which uses the default keys `password, secret, api_key, session_token, authorization`. But the unmasked payload is written to the database and returned in the POST response first.

**The path from the request to a case or filter:**

1. **`POST /api/v1/{organization}/signals/instances`**, `create_signal_instance` in `src/dispatch/signal/views.py:70-120`. It resolves the project and the signal definition (by variant or external id, falling back to the default). It then calls `signal_service.create_instance` and commits. The route does not call any flow and does no masking.

2. **`create_instance`** in `src/dispatch/signal/service.py:~650-705`. It stores `raw` as a JSON round-trip of the input (line ~680). Nothing is redacted here, so **the plaintext payload is committed to the `signal_instance.raw` JSONB column at this point.** It also sets the id and the priority, type, and oncall fields, then adds the row to the session.

3. **Background worker**, `process_signals` in `src/dispatch/cli.py:938`. It loops over instances with `filter_action IS NULL` and `case_id IS NULL`, oldest first, up to 500 per pass. For each one it calls `signal_flows.signal_instance_create_flow` and commits. I did not check how this worker is deployed or scheduled.

4. **`signal_instance_create_flow`** in `src/dispatch/signal/flows.py:~44`. Its first real step is line 60: `signal_instance.raw = redact_raw(signal_instance.raw)`. The comment says this happens "before entities are extracted from the payload". Entity extraction, `entity_service.find_entities`, therefore sees the masked payload. After that:
   - Entity extraction runs if any entity types apply, followed by a commit.
   - `signal_service.filter_signal` runs snooze and dedup filters. It always commits at the end. If a filter matched, the flow returns here.
   - Canary instances and signals with `create_case` off are returned without a case.
   - Otherwise a case is created with `CaseCreate` (visibility open, status new), `signal_instance.case = case`, and a commit. Case-created flows follow.

**Where masking happens:** `redact_raw` in `src/dispatch/signal/redaction.py:10-15`, called only from `flows.py:60`. It returns a copy of the input. The function matches keys case-insensitively, at any depth, through dicts and lists. Values under a matching key become `"[REDACTED]"`. Other scalars, including strings that contain secrets, are returned unchanged.

**Default keys:** `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98-102`, overridable by env var as a comma-separated list. The default is `password,secret,api_key,session_token,authorization`. Blank entries are ignored.

**Is the unmasked payload written to the database?** Yes, in two places before the flow runs:
- The `create_instance` commit in the POST route stores the raw payload in the row.
- The POST response (`SignalInstanceRead`, which includes `raw: dict`) returns the raw payload to the caller.

The worker later overwrites the same column with the masked version and commits. So the row ends up masked, but the plaintext is in the row, in the WAL, and in any backup taken in the window between ingest and processing. I found no separate table or log that keeps a copy, but I did not search the logs or the rest of the codebase for other writes of `raw`.

**Gaps I noticed (not changed):**
- Matching is exact after lowercasing. `apiKey`, `api-key`, `x-api-key`, `token`, `private_key`, and `cookie` are not masked by default.
- Only keys are checked, not values. A secret inside a free-text field is not masked.
- If the worker is not running, or the instance fails processing, the plaintext stays in the row. The flow's exception handler rolls back and logs, and it does not retry masking.

----- next turn -----

The regression came from commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02). It changed the JSONPath lookup in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`, around line 289) to `jpath.find(signal_instance.raw)[:1]`. That slice keeps only the first match, so every other field matching the same JSONPath was dropped.

I reverted that line to `matches = jpath.find(signal_instance.raw)`. The `[:1]` and its comment are gone, and the file now differs from the parent commit only by reverting that change.

`python -m pytest tests/entity` now passes: 11 passed. Before the fix, `test_find_entities_with_field_only` failed with `assert 1 == 2`. I didn't change any tests.

Nothing is committed. Earlier uncommitted work is still in the tree: the incident `delete_custom_event` permission restore with its test in `tests/incident/`, and the restricted-case visibility fix in `src/dispatch/database/service.py`. I did not run the full suite, only `tests/entity`.

----- next turn -----

Found it. The flow masks the payload before entity extraction, so the JSONPath matched the masked placeholder string `"[REDACTED]"`. The extractor accepted it as an ordinary string value. Every instance with that signal then got the same `[REDACTED]` entity, and the deduplication filter grouped them into one case.

**Fix:** In `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`), a match is now skipped if its value equals `MASK` from `dispatch.signal.redaction`. Masking itself is unchanged. This is the only extraction path in `find_entities`, so the check covers every caller, including the entity-type recalculation flow. I didn't find a regex-based extractor in the code.

**Test:** `tests/entity/test_entity_masking.py` is a new file. It redacts `{"session_token": "ghp_secret_value"}`, runs `find_entities` with a `session_token` JSONPath entity type, and asserts that no entity is created. It fails without the fix (the `"[REDACTED]"` entity is created) and passes with it. I didn't modify any existing tests.

**Results:** `python -m pytest tests/entity tests/signal` gives 44 passed and 1 skipped.

**Points to check:**
- Any real value that is exactly `"[REDACTED]"` will also be skipped as an entity. I think that's acceptable, since that string is the mask.
- Entities already created from masked values in the database, for example a `[REDACTED]` entity linked to existing cases, are not cleaned up by this change. Those rows will need a separate cleanup if they matter.
- Nothing is committed. The earlier uncommitted changes are still in the tree.

----- next turn -----

## Recap

**1. Unguarded mutating routes and the incident regression**

I listed the POST, PUT, PATCH and DELETE routes in `case/views.py` and `incident/views.py` that have no `PermissionsDependency`. Four were unguarded before my changes, and one was a regression:

- `create_case`, `create_incident`: open by design, since anyone may report a case or an incident.
- `create_case_channel`, `create_case_resources`: unguarded but never removed by a commit. I flagged these as an open design question and did not change them.
- `delete_custom_event` (incident): its permission check was removed by `28c21e1e` ("refactor(incident): tidy custom event routes"). I restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` and added `tests/incident/test_incident_event_permissions.py`. The test fails on the regressed code and passes with the fix.

**2. Cases list showing restricted cases to non-participants**

`restricted_case_filter` in `src/dispatch/database/service.py` lost its `and_` guard in `42699ebc` ("refactor(database): flatten the restricted case filter"). The restricted clause then matched every restricted case. The original guard came from `b05613b5` (sec(authz)). I restored it so a restricted case matches only when the user is a participant. The existing `test_restricted_case_filter_with_test_data` catches the regression.

**3. Signal instance flow: masking and entity extraction**

- **Where masking happens:** `redact_raw` in `src/dispatch/signal/redaction.py`, called from `signal_instance_create_flow` in `src/dispatch/signal/flows.py` before entity extraction. Masking was introduced in `d2675cf4` ("feat(signal): mask sensitive raw fields before processing").
- **Default keys:** `password, secret, api_key, session_token, authorization` (`SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`).
- **Unmasked payload in the database:** yes. `create_instance` commits the raw payload, and the POST response returns it. The worker overwrites the column with the masked version later, so the plaintext persists until processing.
- **Extraction bug:** `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath lookup, so only the first matching field became an entity. I reverted that line. `tests/entity` passes (11 tests).
- **Masked values as entities:** the flow masks the payload before extraction, so a JSONPath pointing at a masked key matched the placeholder `"[REDACTED]"`. Every instance then got the same entity, and the deduplication filter grouped them. Extraction now skips values equal to `MASK`, and `tests/entity/test_entity_masking.py` covers this. `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**Open items:**
- Entities already created from masked values stay in the database and need a separate cleanup.
- The two unguarded case routes still need a decision.
- Nothing is committed. Uncommitted changes: the incident permission restore and its test, the cases-list visibility fix, the entity revert, the masked-value check, and the new test files.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4