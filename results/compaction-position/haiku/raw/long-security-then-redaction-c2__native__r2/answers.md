Five mutating routes have no `PermissionsDependency` in their route definition:

**`src/dispatch/case/views.py`**
1. `POST ""`: `create_case` (line 162)
2. `POST /{case_id}/resources/conversation`: `create_case_channel` (line 236)
3. `POST /{case_id}/resources`: `create_case_resources` (line 260)

**`src/dispatch/incident/views.py`**
4. `POST ""`: `create_incident` (line 117)
5. `DELETE /{incident_id}/event/{event_uuid}`: `delete_custom_event` (line 503)

The case and incident routers are mounted under `authenticated_organization_api_router` in `src/dispatch/api.py`. That parent router adds only `get_organization_path`, which is a path-validation stub, not a permission check. So the five routes above have no permission check at any level I could find. I did not change any code.

----- next turn -----

One route was a regression, and I've restored its check and added a test that fails if it goes missing again.

**The regression:** `DELETE /incidents/{incident_id}/event/{event_uuid}` (`delete_custom_event`) lost its `IncidentEventPermission` check in commit `28c21e1e` ("refactor(incident): tidy custom event routes"). That commit was labelled a refactor and removed only the `dependencies=` line. The other custom-event routes in the same file still have the check.

**Not regressions:**
- `POST /cases/{case_id}/resources` and `POST /cases/{case_id}/resources/conversation` never had a permission check. They were added without one.
- `POST /cases` and `POST /incidents` are the open reporting routes you described.

**Changes:**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on `delete_custom_event`.
- `tests/incident/test_incident_event_permissions.py` (new): checks that the DELETE route on `/{incident_id}/event/{event_uuid}` carries a `PermissionsDependency` with `IncidentEventPermission`. It reads the route definition rather than making HTTP calls.

**Verification:**
- The new test passes with the fix.
- I removed the check temporarily and the test failed, then I restored the fix.
- `python -m pytest tests/incident tests/case` passes (16 tests).

I haven't committed anything. The two case resource routes still have no check, and I left them alone. If they should be guarded, that's a separate change.

----- next turn -----



----- next turn -----

The cause is commit `42699ebc` ("refactor(database): flatten the restricted case filter"). It removed the `and_(...)` around the restricted-case condition in `restricted_case_filter` (`src/dispatch/database/service.py`). The filter now reads:

```python
Case.visibility == Visibility.open,
Case.visibility == Visibility.restricted,   # no participant check
IndividualContact.email == current_user.email,
```

Those are `or_` terms, so any restricted case matched for any non-admin user, whether or not they were a participant. The incident filter in the same file still has the `and_`, which is how the bug stood out.

**Fix:** I restored the `and_(...)` wrapper exactly as the code had it before `42699ebc`. No tests were changed.

**Verification:**
- `python -m pytest tests/case tests/database tests/incident -q`: 41 passed with the fix.
- Against the buggy HEAD version, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` fails: "Member should see 3 cases (2 open + 1 restricted as participant), got 4". So the existing test already catches this regression, and I didn't need to add one.

Nothing is committed. The working tree now has this fix alongside the earlier `delete_custom_event` fix and the new test in `tests/incident/`. Do you want these committed, and as one commit or two?

----- next turn -----

Masking happens in a background processing step, not at intake. The unmasked payload is written to the database when the request is accepted, and it is returned in the API response.

**Trace**

1. **Route** `POST /signals/instances` (`src/dispatch/signal/views.py:70`). It resolves the project and signal definition, then calls `signal_service.create_instance` and `db_session.commit()`. The response model is `SignalInstanceRead`, which inherits `raw` from `SignalInstanceBase`. The raw payload is not masked here.

2. **Storage** (`src/dispatch/signal/service.py:650`). `create_instance` copies the raw payload, drops `oncall_service` if present, and round-trips it through JSON. It stores the result in `SignalInstance.raw` (JSONB, `models.py:239`) without masking.

3. **Processing** happens later and separately. Nothing in the route calls `signal_instance_create_flow`. It runs from:
   - the organization loop, `process_organization_signals` → `process_signal_batch` (`signal/flows.py:385–428`), started by `main_processing_loop` (`flows.py:441`); or
   - a CLI path (`src/dispatch/cli.py:1004`).

   Both select rows with `filter_action IS NULL` and `case_id IS NULL`.

4. **Masking** happens in `signal_instance_create_flow` (`signal/flows.py:59–60`):
   ```python
   signal_instance.raw = redact_raw(signal_instance.raw)
   ```
   This runs before entity extraction, so entities are found from the masked payload.

5. **Redaction function**: `redact_raw` in `src/dispatch/signal/redaction.py`. It returns a new structure. Key names are compared case-insensitively, at any depth, through dicts and lists. Matching keys get the value `"[REDACTED]"`. Other values are unchanged.

6. **Default keys** come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98`, overridable by environment variable:
   `password, secret, api_key, session_token, authorization`
   Matching is on whole key names, so `apikey`, `api-key`, `token`, `cookie` or `private_key` are not masked by default.

7. **Filter and case creation.** `signal_service.filter_signal` (`service.py:866`) applies snooze and deduplication and commits. If the instance is not filtered, the flow checks canary status and `create_case`. It then calls `case_service.create` with the signal's name and description, not the raw payload. The instance is linked to the case, which is the "opens a case" outcome. Filtered instances stop at step 7 with a `filter_action`.

**Is the unmasked payload written to the database?** Yes. The route's `db_session.commit()` persists the raw payload as sent, before any masking. The masked version is only written later, when a processing commit flushes the reassigned `raw`, typically in `filter_signal`'s commit. Until processing runs, the unmasked row remains in the table, and it is returned in the create response, because `SignalInstanceRead` includes `raw`.

I found no test that covers `redact_raw` (`grep -rln redact tests/` returned nothing). I did this by reading the code and did not run anything. I changed no code.

Do you want a change here? The ways to address it are masking in the route before `create_instance`, or masking in `create_instance` itself. Either would also change the create response and the stored row, and I'd want your decision on whether the default key list should be wider.

----- next turn -----

The change responsible is `beb60cc4` ("perf(entity): stop at the first JSONPath match"). It added `[:1]` to the JSONPath lookup in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`), so only the first matching field became an entity. I removed the slice, which restores `jpath.find(signal_instance.raw)` as it was before that commit.

**Verification**
- Before the fix, `tests/entity` had one failure: `test_find_entities_with_field_only` expected 2 entities and got 1.
- After the fix, `python -m pytest tests/entity tests/incident tests/case tests/database tests/signal -q` gives 84 passed, 1 skipped.
- No test files were changed.

The commit is dated 2025-09-02, not this week. If your CI red started this week, the commit may have reached main later than its date suggests, or something else changed too. I only checked this commit's diff and the failing test.

**Current working tree**, all uncommitted:
- `src/dispatch/entity/service.py`: the entity fix above.
- `src/dispatch/database/service.py`: the case-visibility fix from earlier.
- `src/dispatch/incident/views.py`: the `delete_custom_event` permission restore from earlier.
- `tests/incident/test_incident_event_permissions.py`: the new regression test (untracked).

Do you want these committed? If so, I'd suggest one commit per fix.

----- next turn -----

The cause is in `find_entities` (`src/dispatch/entity/service.py`). When a JSONPath matches a sensitive field, the entity is built from the masked placeholder, so every such instance gets the same entity value `"[REDACTED]"`. Deduplication on that entity then groups unrelated tokens into one case.

**Fix**
- `find_entities` now masks the payload itself, using `redact_raw`, before running the JSONPath. Extraction always sees masked input, no matter which caller invokes it.
- It also skips any string value equal to `MASK`, so a placeholder can't become an entity.
- The masking function and its default keys are unchanged.

**Why this location:** the flow in `signal/flows.py` already masked `raw` before extraction, but `entity_type/service.py` and `entity_type/flows.py` call `find_entities` on raw payloads that may never have been masked. Putting the masking in `find_entities` covers all three callers.

**Test:** `tests/entity/test_entity_masked_values.py` (new). It stores a `session_token` and a `user` in one payload, with entity types on both fields. It asserts that only the user becomes an entity. I ran it against the committed `HEAD` version of `service.py`, and it failed. With the fix, it passes.

**Results:** `python -m pytest tests/entity tests/signal tests/entity_type tests/incident tests/case tests/database -q` gives 91 passed, 1 skipped.

**Not verified:** I didn't reproduce the production grouping directly. The test shows the mechanism, not the production data.

Uncommitted changes in the working tree now include this fix. Do you want them committed?

----- next turn -----

## Recap

**1. Permission audit (case and incident APIs)**
I listed every POST, PUT, PATCH, and DELETE handler in the case and incident routers that had no `PermissionsDependency`. Two of the five are intentional open reporting routes: `create_case` and `create_incident`. The other three are not all regressions:
- `create_case_channel` and `create_case_resources` never had a check, so they are gaps from when they were added, not regressions.
- `delete_custom_event` lost its `IncidentEventPermission` check in `28c21e1e` ("refactor(incident): tidy custom event routes"). That commit was labelled a refactor, and it only removed the `dependencies=` line.

I restored the check on `delete_custom_event` and added `tests/incident/test_incident_event_permissions.py`. The test fails when the check is removed and passes with it. I left the two unguarded case resource routes alone; they need a decision on whether they should be guarded.

**2. Restricted cases visible to non-participants**
`restricted_case_filter` in `src/dispatch/database/service.py` lost its `and_(...)` wrapper in `42699ebc` ("refactor(database): flatten the restricted case filter"). Any restricted case then matched for any non-admin user. I restored the wrapper. The existing `tests/database/test_service.py::test_restricted_case_filter_with_test_data` fails on the buggy version and passes with the fix, so no new test was needed.

**3. Signal instance path and masking**
A signal instance is accepted by `POST /signals/instances`, which stores the raw payload and returns it. Processing runs later. In `signal_instance_create_flow`, `redact_raw` masks the payload before entity extraction, and the flow then either filters the instance or creates a case. Masking matches key names case-insensitively, at any depth, and the default keys are `password, secret, api_key, session_token, authorization`. The unmasked payload is written to the database when the instance is created, and it is returned in the create response.

**4. Entity extraction returns only the first match**
`beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath lookup, so only the first match became an entity. I removed the slice. `tests/entity` was red before and passes now.

**5. GitHub PAT signal grouping**
When a JSONPath matched a masked field, the placeholder `"[REDACTED]"` became an entity value. Every such instance then shared that entity and was deduplicated into one case. `find_entities` now masks the payload itself before extraction and skips any value equal to the mask. Masking is unchanged. The new test is `tests/entity/test_entity_masked_values.py`, and it fails without the fix.

**Test results:** `python -m pytest tests/entity tests/signal tests/entity_type tests/incident tests/case tests/database -q` gives 91 passed, 1 skipped.

**Uncommitted:** the changes listed above are in the working tree, along with the two new test files. Nothing is committed.

**Open item:** the two case resource routes still have no permission check.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4