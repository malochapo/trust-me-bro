Five endpoints change data without a `PermissionsDependency` in their route definition:

1. `POST /case/` — `create_case` (`src/dispatch/case/views.py:162`)
2. `POST /case/{case_id}/resources/conversation` — `create_case_channel` (`src/dispatch/case/views.py:236`)
3. `POST /case/{case_id}/resources` — `create_case_resources` (`src/dispatch/case/views.py:260`)
4. `POST /incident/` — `create_incident` (`src/dispatch/incident/views.py:117`)
5. `DELETE /incident/{incident_id}/event/{event_uuid}` — `delete_custom_event` (`src/dispatch/incident/views.py:503`)

I only checked the route decorators. Each function body may still enforce access in code, and I did not check that. No code was changed.

----- next turn -----

One of the five was a regression, and I've restored its check.

**The regression: `DELETE /incident/{incident_id}/event/{event_uuid}`** (`delete_custom_event`)
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]`. The commit only touched that one line, so the removal was not an intentional access change.
- Before that commit, the route required `IncidentEventPermission`, which allows organization admins and incident commanders or scribes. The other custom-event routes in the file still have it.
- Fix: I restored the same line in `src/dispatch/incident/views.py`.

**Test:** `tests/incident/test_incident_event_permissions.py` looks up the route and asserts that `IncidentEventPermission` is in its `PermissionsDependency`. It passes with the fix and fails when the fix is removed. `python -m pytest tests/case tests/incident tests/incident_role` gives 21 passed.

**The other candidates are not regressions:**
- `POST /case/{case_id}/resources/conversation` (`create_case_channel`, added in `ced74f33`) and `POST /case/{case_id}/resources` (`create_case_resources`, added in `f08a22b3`) were both added without a permission check. The history shows no commit that removed one, so I left them alone. They may still be an oversight, and it's worth a decision on whether they should require an edit permission.
- `POST /case/` and `POST /incident/` are the reporting endpoints you described as open on purpose.

I did not run the full test suite, only the case and incident directories.

----- next turn -----

The cases list was showing restricted cases to people who aren't participants. The fix is in and the tests pass.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` let every restricted case through for non-admin roles. The participant check was only applied to the `IndividualContact.email` clause, and it sat beside the restricted-visibility check instead of being joined to it with `and_`.

**Introduced by:** commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2025-09-02). It was presented as a cleanup, but it removed the `and_(...)` wrapper and changed the access rule. The incident filter never had this change, and it's still correct.

**Fix:** I restored the `and_(Case.visibility == Visibility.restricted, IndividualContact.email == current_user.email)` grouping. Member-level users now see open cases plus restricted cases they participate in.

**Verification:**
- Before the fix, `test_restricted_case_filter_with_test_data` failed with `assert 4 == 3`.
- After the fix, `python -m pytest tests/database/test_service.py tests/case tests/incident` passes (41 tests).
- I didn't touch any existing tests.

The working tree also still has the earlier change: the `dependencies=` restore on `delete_custom_event` in `src/dispatch/incident/views.py`, plus the new test in `tests/incident/`. Nothing is committed.

----- next turn -----

Short answer: the unmasked payload is written to the database. The API commits the raw payload as sent, and masking happens later, in a background worker, which overwrites it. Nothing has been changed.

**Path through the API**

1. `POST /api/v1/{organization}/signals/instances` goes to `create_signal_instance` in `src/dispatch/signal/views.py`. It resolves the project and the signal definition, then calls `signal_service.create_instance` (`src/dispatch/signal/service.py:650`).
2. `create_instance` copies `raw` with `json.loads(json.dumps(...))` and stores it on the `SignalInstance` (`service.py:680`). It does not mask anything.
3. The view calls `db_session.commit()` right after that. The row is now saved with the original, unmasked `raw`.
4. The response (`SignalInstanceRead`) echoes `raw` back to the caller, also unmasked.

The POST never opens a case. It only stores the row. A separate loop does the rest:

5. `signals process` (`src/dispatch/cli.py:938`) runs continuously. It selects up to 500 instances where `filter_action` and `case_id` are null and calls `signal_flows.signal_instance_create_flow` on each (`cli.py:1004`). `flows.py:406` contains a second copy of this loop.
6. `signal_instance_create_flow` (`src/dispatch/signal/flows.py`) first runs `signal_instance.raw = redact_raw(signal_instance.raw)` (`flows.py:60`), before entity extraction, filtering, canary handling and case creation.
7. Entity extraction runs on the redacted payload. JSONPath matching in `src/dispatch/entity/service.py:290` therefore sees `[REDACTED]` for masked keys.
8. `filter_signal` (`src/dispatch/signal/service.py:866`) runs snooze and dedup. If the instance is filtered, it is returned there. Otherwise, a canary is returned after storage, and an instance with `create_case` off is returned without a case. Only the rest of the flow opens a case.

**Where masking happens:** `redact_raw` in `src/dispatch/signal/redaction.py`. It uses a recursive helper `_redact` that walks dicts and lists. Keys are matched case-insensitively, at any depth, and the value is replaced with `[REDACTED]`.

**Default keys:** `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98`, overridable by environment variable:
`password, secret, api_key, session_token, authorization`

Matching is exact key-name equality after lowercasing, not substring matching. So `apiKey`, `x-api-key`, `token` or `access_token` are not masked by default.

**Is the unmasked payload written to the database?** Yes, in two ways:
- **Immediately, by the API.** The view commits the raw payload before any masking runs. Anyone with database access, backups, or WAL can see the original values until the worker processes that row.
- **Overwritten later.** The worker stores the masked payload when it commits (`filter_signal` commits at `service.py:896`, and the entity path commits at `flows.py`). After that, the row holds the masked version. Earlier versions can still exist in backups or WAL.

The exposure window is as long as the instance waits for `signals process`. If that worker is down or behind, the unmasked values stay in the table.

**Things I did not verify**
- `update_instance` (`service.py:730`) writes `raw` back unmasked. I did not check whether any API route reaches it.
- I did not trace the case-creation branch past the checks shown above.
- I did not check whether the logging or search indexing paths see the payload before masking.

----- next turn -----

Entity extraction is fixed. The change responsible is commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02).

**Cause:** the commit changed `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]` in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`). The comment said a JSONPath names one field, which is wrong for wildcards, recursive descent and filters, so every match after the first was silently dropped.

**Fix:** I removed the `[:1]` slice and its comment, so the function again yields one entity for every string match. The diff against HEAD is just those two lines.

**Verification:**
- Before the fix, `tests/entity` had one failure: `test_find_entities_with_field_only`.
- After the fix, `python -m pytest tests/entity` passes (11 tests), and `tests/entity` plus `tests/database/test_service.py` pass together (36 tests).
- I didn't change any tests.

The working tree also still contains the earlier fixes: the `and_` restore in `src/dispatch/database/service.py`, the `dependencies=` restore on `delete_custom_event` in `src/dispatch/incident/views.py`, and the new test in `tests/incident/`. Nothing is committed.

----- next turn -----

Masked values no longer become entities, so the deduplication filter can no longer group unrelated instances on `[REDACTED]`.

**Why it happened:** the masking step replaces a sensitive value with the string `"[REDACTED]"`. The entity JSONPath for the session token then matched that string like any other value. Every instance got an entity with the same value, and the dedup filter grouped them on it. The masking itself was working.

There are two entry points for extraction. The signal flow masks the payload before calling `find_entities`. `entity_type/service.py` (for stored instances) calls `find_entities` directly, so it bypassed that step.

**Fix** (`src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression`):
- The payload is masked inside the matcher with `redact_raw`, so every caller is covered.
- Matches whose value equals `MASK` are skipped.
- The masking in `redaction.py` and in the signal flow is unchanged.

**Test:** `tests/entity/test_entity_redaction.py` has two cases. One checks that a session-token path yields no `[REDACTED]` or raw secret while a normal field is still extracted. The other checks that an already-masked value is skipped. Both fail on the previous code and pass now.

**Verification:** `python -m pytest tests/entity tests/entity_type tests/signal tests/database tests/case tests/incident` gives 92 passed and 1 skipped.

**Not done:**
- Entities already created from `[REDACTED]` are still in the database and still attached to the affected instances. Those need a data cleanup, which I did not run.
- `entity_type/flows.py:29` assigns the result of `signal_instance.signal.entity_types.append(entity_type)`, which is `None`. The `if entity_types:` block after it therefore never runs. It looks like a separate existing bug, and I did not change it.

Nothing is committed. The working tree also still holds the earlier fixes from this session.

----- next turn -----

## Recap

**Access review (case and incident API)**
- Five data-changing routes had no `PermissionsDependency`. Two are reporting endpoints that are open by design (`case.create_case`, `incident.create_incident`). The other three were not protected from when they were added: `case.create_case_channel`, `case.create_case_resources` and `incident.delete_custom_event`.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` ("tidy custom event routes") removed its `IncidentEventPermission` check. I restored it and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again.
- The two case routes had no check from the start (`ced74f33`, `f08a22b3`), so I left them. Whether they should require edit rights is a decision for the team.

**Restricted cases visible to non-participants**
- `restricted_case_filter` in `src/dispatch/database/service.py` let members see every restricted case. Commit `42699ebc` ("flatten the restricted case filter") dropped the `and_` that required participation. I restored it. The existing test went from `assert 4 == 3` to passing.

**Signal trace (POST `/signals/instances`)**
- The API stores the raw payload and commits it. Masking happens later, in `signal_instance_create_flow`, when the `signals process` worker runs. The masked payload then overwrites the stored one.
- `redact_raw` in `src/dispatch/signal/redaction.py` does the masking. Default keys are `password, secret, api_key, session_token, authorization`. Matching is exact on the key name, so variants such as `apiKey` are not masked.

**Entity extraction and shared "[REDACTED]" entities**
- Commit `beb60cc4` added `[:1]` to the JSONPath match, so only the first match became an entity. I removed the slice. `tests/entity` is green again.
- Masked values became entities because the JSONPath matched the `"[REDACTED]"` string. Every instance then got the same entity, and the dedup filter grouped them. `find_entities` now masks the payload itself and skips masked values. This covers the stored-instance path in `entity_type/service.py`, which bypassed the flow's masking. The new test is `tests/entity/test_entity_redaction.py`.
- Still open: entities already created from `[REDACTED]` need a data cleanup. `entity_type/flows.py:29` also has a separate bug, where `append()` returns `None` and the block after it never runs.

Nothing is committed. Earlier changes and the new tests are in the working tree.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4