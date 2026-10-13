Five state-changing routes do not declare a `PermissionsDependency` in their route definition:

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
3. `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident` (line 117)
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

I only checked the route decorators. I did not read the function bodies, so these routes may still enforce access inside the handler or in a service call. The router-level `get_organization_path` dependency in `src/dispatch/api.py:97-100` is an empty `pass` function, so it does not enforce permissions. No code was changed.

----- next turn -----

One of the five routes was a regression, and it's restored. The other four were never protected, so I left them as they are.

**Regression: `DELETE /incidents/{incident_id}/event/{event_uuid}` (`delete_custom_event`)**
- Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]`. The diff is a single deleted line, and the commit message describes no behaviour change.
- Fix: restored that line in `src/dispatch/incident/views.py`, matching the other event routes in the file.
- Test: `tests/incident/test_incident_event_permissions.py` looks up the DELETE route on the incident router and asserts that its dependencies include a `PermissionsDependency` carrying `IncidentEventPermission`. I ran it against the pre-fix file, where it failed, and against the fixed file, where it passed. The new test and the existing `tests/case/test_case_event_views.py` pass together (5 tests).

**Not regressions**
- `POST /cases/{case_id}/resources` (`create_case_resources`) was added in `f08a22b3` with no permission and has never had one.
- `POST /cases/{case_id}/resources/conversation` (`create_case_channel`) was added in `ced74f33` with no permission and has never had one.
- The `CaseViewPermission` that appears in `89d58249` belongs to the participant GET routes, not these.
- `POST /cases` and `POST /incidents` are the open-to-reporters routes you mentioned.

These two case routes lack a check, but I found no removal commit, so I'd treat them as a possible gap in the design rather than a regression. Deciding whether they need one is your call.

I ran only the two test files above, not the full suite. The test was written with the `tests/case` layout in mind, so it has no `__init__.py`, matching that folder.

----- next turn -----

The cases list leaked restricted cases because of commit `42699ebc` ("refactor(database): flatten the restricted case filter", Sam Ortega, 2 Sep 2025). That commit is the one that introduced the bug.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` checks visibility before participation. Before `42699ebc`, a restricted case passed the filter only when the user's email matched a participant on it:

```python
and_(
    Case.visibility == Visibility.restricted,
    IndividualContact.email == current_user.email,
),
```

`42699ebc` removed the `and_(...)` wrapper, so `Case.visibility == Visibility.restricted` became a standalone `or_` branch. Every restricted case then matched for any non-admin user, whether or not they were a participant. The incident filter does not have this problem.

**Fix:** I restored the `and_(...)` grouping in `restricted_case_filter`. No other code or tests changed.

**Verification:**
- Before the fix, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` failed with `assert 4 == 3`. A member saw four cases where three were expected.
- After the fix, `tests/database/test_service.py`, `tests/case`, and `tests/incident` pass (41 tests). That run includes the permission test from the previous step.

Nothing is committed. The working tree has the two source changes from this and the previous step, plus the new `tests/incident/` directory.

----- next turn -----

A signal instance sent to `POST /api/v1/{organization}/signals/instances` is stored with its raw payload unmasked. Masking happens later, in the background processor, which overwrites the stored copy. No code was changed.

**1. API request (synchronous)**
- `create_signal_instance` (`src/dispatch/signal/views.py:70`) resolves the project and signal definition. It looks up the definition by `externalId`/`variant`, falls back to the default, and returns 404 if neither exists.
- `signal_service.create_instance` (`src/dispatch/signal/service.py:650`) stores `raw` as given, after a JSON round-trip (line ~680). It is added to the session with no masking.
- The view commits (`views.py` ~line 119). **This is the first point where the unmasked payload reaches the database.**
- The response is `SignalInstanceRead`, which includes `raw` (`src/dispatch/signal/models.py:394, 408`). The sender gets the unmasked payload back.

**2. Background processing (asynchronous)**
- Instances with `filter_action IS NULL` and `case_id IS NULL` are picked up by `main_processing_loop` and `process_organization_signals` (`src/dispatch/signal/flows.py:441`, ~428), or by the CLI command `signals process` (`src/dispatch/cli.py:937`, ~1004). Each one goes through `signal_instance_create_flow` (`flows.py:46`).
- **Masking:** `flows.py:60` runs `signal_instance.raw = redact_raw(signal_instance.raw)`. This happens before entity extraction, and the masked value is committed at the entity step (`flows.py` ~70) or in `filter_signal`'s commit (`service.py:896`).
- Then `filter_signal` (`service.py:866`) applies snooze and deduplication. A filtered instance returns there.
- Canary instances return next. Instances whose signal has `create_case` false also return.
- Otherwise the flow goes on to create or attach a case. I did not trace the case-creation code.

**Masking function**
- `redact_raw` in `src/dispatch/signal/redaction.py:10` is the entry point. It calls the recursive `_redact` (line 20).
- Keys are matched exactly, case-insensitively, at any depth, inside dicts and lists. A match replaces the value with `"[REDACTED]"`. Substrings do not match: `apiKey` lowercases to `apikey`, which is not `api_key`. Values inside strings are not scanned.
- **Default keys** come from `src/dispatch/config.py:98-101`: `password, secret, api_key, session_token, authorization`. The `SIGNAL_REDACTED_RAW_FIELDS` environment variable overrides them as a comma-separated list.

**Is the unmasked payload written to the database?** Yes. It is written at API time, and it persists until the processor reaches the instance and overwrites it with the masked version. Two gaps follow from this:
- Until the processor runs, the row holds the raw payload. The processing delay sets how long that lasts.
- If processing fails for an instance, it keeps the unmasked payload. The batch query selects it again on each run, but the failing instance is not masked unless processing succeeds. I did not confirm how the loop handles repeated failures.

`signal/service.py:update_instance` (line 726) writes `raw` without calling `redact_raw`, but nothing in `src/dispatch` calls it, so I did not treat it as part of the request path.

----- next turn -----

Entity extraction is fixed. The change responsible is `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2 Sep 2025).

**Cause:** in `find_entities` (`src/dispatch/entity/service.py`), the commit changed `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. Every JSONPath therefore produced at most one entity, even when it matched several fields.

**Fix:** I removed the `[:1]` slice and the comment that came with it, so the loop again yields every string match. Nothing else changed in that function.

**Verification:**
- Before the fix, `tests/entity` had one failure: `test_find_entities_with_field_only` expected 2 entities and got 1.
- After the fix, `tests/entity` passes (11 tests).
- `tests/signal`, `tests/case`, `tests/incident`, and `tests/database` also pass (73 passed, 1 skipped).

The commit's stated goal was performance. Removing the slice means extraction returns all matches again, which is the behaviour the tests expect. If the slowdown the commit targeted matters, it needs a different fix, such as capping matches per entity type, and that would need its own test. I didn't pursue that.

**Working tree:** this session's changes are still uncommitted. They are the `restricted_case_filter` fix in `database/service.py`, the delete-route permission in `incident/views.py`, the entity fix above, and the new `tests/incident/` directory.

----- next turn -----

Masked values no longer become entities. The cause was in entity extraction, not in the masking itself. The flow masks the payload and then runs `find_entities` on it. The session token became the placeholder `"[REDACTED]"`, so every masked instance produced the same entity value. The deduplication filter on that entity then grouped unrelated instances together.

**Root cause:** `find_entities` extracted from `signal_instance.raw` as given. `signal_instance_create_flow` masks the payload before calling it, so the extracted value was the placeholder.

**Second path:** the bug is wider than the flow. Called on an unmasked payload, `find_entities` extracted the raw secret. The entity-type code calls it with stored payloads, and `redact_raw` is not applied there, so that path can leak the secret into entities directly.

**Fix** (`src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression`):
- Extraction now runs on `redact_raw(signal_instance.raw)`, so the secret is never read.
- Matches equal to `MASK` are skipped, so a masked field yields no entity.
- Masking itself is unchanged: `redaction.py` and `signal/flows.py` are untouched.

**Test:** `tests/entity/test_entity_masking.py` calls `find_entities` directly on a payload that still contains the secret. It asserts that neither the secret nor the placeholder becomes an entity, and that a non-sensitive `externalId` still does. The test failed before the fix, where the secret was extracted, and passes now. The existing tests are unchanged.

**Verification:** `tests/entity`, `tests/signal`, `tests/case`, `tests/incident`, and `tests/database` pass (85 passed, 1 skipped).

**Side effect to know about:** any literal string equal to `"[REDACTED]"` in a non-sensitive field is no longer extracted as an entity either. I judged that acceptable.

**Not verified:** I did not check whether a deduplication rule on entities already matches on `"[REDACTED]"` in stored data. Entities created before this fix still carry that value, so they would need a cleanup to stop grouping.

The uncommitted working-tree changes are now the `restricted_case_filter` fix, the delete-route permission, the entity fixes, and the new test files under `tests/incident/` and `tests/entity/`.

----- next turn -----

The recap is below. Nothing is committed yet, and all the changes are in the working tree.

**1. Permission review (write routes without a `PermissionsDependency`)**
Five handlers changed data without a declared permission: `create_case`, `create_case_channel`, `create_case_resources`, `create_incident`, and `delete_custom_event`. Reporting a case or incident is open by design. The two case resource routes were never protected, so they're a gap to decide on, not a regression. `delete_custom_event` was a regression: commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_event_permissions.py`, which fails if the check goes missing again. It fails on the pre-fix file and passes after the restore.

**2. Restricted cases visible to non-participants**
The cases list leaked restricted cases to members who were not participants. Commit `42699ebc` ("refactor(database): flatten the restricted case filter") removed the `and_(...)` grouping in `restricted_case_filter`. That turned the restricted branch into a match for every non-admin. I restored the grouping. `test_restricted_case_filter_with_test_data` failed with 4 where 3 were expected, and passes now.

**3. Entity extraction keeping only the first match**
Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath results, so each entity type produced at most one entity. I removed the slice. `tests/entity` was red and is green now. The performance goal of that commit was not addressed; if it still matters, it needs its own design.

**4. Masked tokens grouping unrelated instances**
Masking happened before extraction, so every masked instance produced the entity value `"[REDACTED]"`, and the deduplication filter grouped them. A direct call to `find_entities` on an unmasked payload also extracted the raw secret. I changed `_find_entities_by_jsonpath_expression` to extract from `redact_raw(...)` and skip the placeholder. The masking code is unchanged. The new test `tests/entity/test_entity_masking.py` failed before the fix and passes now.

**Test status:** `tests/entity`, `tests/signal`, `tests/case`, `tests/incident`, and `tests/database` pass (85 passed, 1 skipped). I did not run the full suite.

**Open items**
- Unmasked payloads are still written to the database when the instance is created. The processor overwrites them with the masked copy later, and a failed instance stays unmasked. I did not change this.
- Entities created before the fix may still hold the value `"[REDACTED]"`. Those need a cleanup before any deduplication rule on them is trusted.
- The two case resource routes still have no permission check.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4