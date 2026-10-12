Four mutating routes declare no `PermissionsDependency`: three in the case API and one in the incident API.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case` (line 162)
2. `POST /{case_id}/resources/conversation` → `create_case_channel` (line 236)
3. `POST /{case_id}/resources` → `create_case_resources` (line 260)

**Incident API (`src/dispatch/incident/views.py`)**
1. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event` (line 503)

I checked every POST, PUT, PATCH and DELETE decorator in both files, including the multi-line ones. All the other mutating routes declare a `PermissionsDependency`. I only looked at the decorators in these two files. Router-level dependencies (set where the router is included, e.g. in `api.py`) or other auth middleware may still apply to these routes. I didn't check that.

----- next turn -----

Yes, one of them is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event` in the incident API). I've restored its check and added a test. Nothing is committed.

**What happened:** commit `28c21e1e`, "refactor(incident): tidy custom event routes", removed `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` from that route. The commit message describes a tidy-up, and the diff is only that one removed line. The sibling routes (create, update and export event) still carry the same check.

**What I changed:**
- **Fix:** I put the `IncidentEventPermission` dependency back on the route in `src/dispatch/incident/views.py`.
- **Test:** the new `tests/incident/test_incident_views.py` looks up that DELETE route and asserts it declares a `PermissionsDependency` containing `IncidentEventPermission`. The existing event tests call the view functions directly, so they would never notice a missing route dependency.
- **Verification:** the test passes with the fix. With the fix stashed it fails, so it does catch the regression.

**The other three:**
- **Open by design:** `create_case` and `create_incident` are the "anyone may report" routes.
- **Case resource routes:** `POST /{case_id}/resources/conversation` and `POST /{case_id}/resources` look like they were never guarded. I only searched for when those two routes were added (`ced74f33` for the channel route, `f08a22b3` for resources) and did not read their diffs for a check. They may be unguarded by oversight, which is a separate question from a regression. The incident equivalent, `create_incident_resources`, uses `IncidentViewPermission`, so you may want to decide whether the case versions should match.

I ran only the new test file, not the full suite.

----- next turn -----

Fixed. The cases list showed restricted cases to non-participants because of a bad rewrite of the filter in `restricted_case_filter` (`src/dispatch/database/service.py`).

**Cause:** commit `42699ebc` (Sam Ortega, 2 Sep 2025), "refactor(database): flatten the restricted case filter", changed the filter's `or_` conditions. They had been:
- `open`, or
- `restricted` and `IndividualContact.email == current_user.email`

It "flattened" them into three separate alternatives:
- `open`
- `restricted`
- `email == current_user.email`

The bare `Case.visibility == restricted` branch is true for every restricted case, so any non-admin user, including the security team member, sees all of them. The email branch also no longer checks visibility. That second branch is harmless on its own, since open cases were already visible. `restricted_incident_filter` still has the correct form, which is why incidents weren't affected.

**Fix:** I put the `and_(restricted, email == current_user.email)` grouping back, which is the same form the filter had before that commit and the same as the incident filter.

**Tests:** I didn't touch the existing tests. `tests/database` and `tests/case` pass (40 tests). I didn't add a regression test for this one, and the existing tests evidently didn't catch the bug. Say if you want me to add one.

The earlier incident `delete_custom_event` fix and its test are still uncommitted in the working tree alongside this change.

----- next turn -----



----- next turn -----

**Yes, the unmasked payload is written to the database.** The API commits it first. Masking happens later, in a separate worker, and that is the only place it happens.

**Trace of `POST /api/v1/{organization}/signals/instances`**

1. **API view** (`signal/views.py:70`, `create_signal_instance`, rate-limited to 1000/min):
   - It resolves the project, then finds the signal definition. It looks up the definition by `raw["externalId"]` or `raw["variant"]`, falls back to the project's default signal, and returns 404 if there is none.
   - It then calls `signal_service.create_instance` and runs `db_session.commit()` (`views.py:117-120`). A duplicate id returns 409.
   - The view never calls the case flow. The `BackgroundTasks` parameter is unused.
2. **`signal/service.py:650`, `create_instance`:**
   - It copies `raw`, round-trips it through JSON (`:680`), builds the `SignalInstance` and adds it to the session. There is no masking here.
   - A `raw["id"]` that is a valid UUID becomes the primary key.
   - The new row has no `filter_action` and no `case_id`.
3. **Worker:** `dispatch signals process` (`cli.py:937`) polls every organization for instances where `filter_action IS NULL` and `case_id IS NULL`. It takes up to 500 per pass, oldest first. A near-identical loop, `main_processing_loop` in `signal/flows.py:~430`, does the same. Both call `signal_instance_create_flow` (`flows.py:46`) for each instance.
4. **`signal_instance_create_flow`:**
   - **Masking:** `signal_instance.raw = redact_raw(signal_instance.raw)` at `flows.py:60`, before entity extraction.
   - **Entities:** it collects the signal's own entity types plus the `all`-scoped ones, extracts entities from the masked payload, and commits (`:70-72`).
   - **Filtering:** `filter_signal` (`service.py:866`) first runs `filter_snooze`. An active snooze filter that hasn't expired, and whose expression matches or is empty, sets `filter_action=snooze`.
     - If not snoozed, `filter_dedup` runs. Canary instances skip dedup.
     - With no filters, it dedups against any non-canary instance of the same signal with a case, within 45 minutes (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`).
     - Otherwise it uses active dedup filters, matching on shared entities within the filter's window.
     - A match sets `filter_action=deduplicate` and attaches the existing `case_id`.
     - No match sets `filter_action=none`. It commits either way.
   - **Filtered:** if the instance was snoozed or deduplicated, it is returned, after refreshing the Slack signal message when a conversation exists.
   - **Not filtered, no case:** canary instances, and signals with `create_case` false, are stored and returned.
   - **Case opened:** otherwise it resolves case type, priority, oncall and conversation target. It then runs `case_service.create` and `case_new_create_flow`. After that it runs engagement for entities and any workflows.

**Masking**
- **Function:** `redact_raw` in `src/dispatch/signal/redaction.py:10`, with the recursive helper `_redact`. It replaces the value with `"[REDACTED]"`.
- **Matching:** keys match case-insensitively and exactly, at any depth, inside dicts and lists. Substrings do not match, so `access_token` is not masked by `session_token`. Secrets embedded in string values are not masked either.
- **Default keys** (`config.py:98`, `SIGNAL_REDACTED_RAW_FIELDS`): `password`, `secret`, `api_key`, `session_token`, `authorization`. The env var of the same name overrides them with a comma-separated list. Setting it replaces the defaults rather than adding to them.

**Is the unmasked payload persisted?**
- **At creation:** yes. `create_instance` stores the raw JSON as sent, and the view commits it at `views.py:120`.
- **How long:** the row stays unmasked until the worker reaches it. If the worker is down or backlogged, it stays unmasked indefinitely.
- **Failed processing:** the worker's flow can fail before its first commit. In that case it rolls back and the row stays unmasked, and the next pass retries it.
- **Response:** the POST response (`SignalInstanceRead`) presumably echoes `raw` unmasked. I didn't read the schema to confirm.
- **Scheduler path:** `create_signal_instance` in `flows.py:231` also stores `raw` unmasked, then relies on the same later pass.

**Other things I noticed**
- `flows.py:55` logs with `"%%s"`, which is a typo. The id is never interpolated into that error message.
- `views.py:86-104` only assigns `signal_definition` when `signal_instance_in.signal` is empty. If a caller supplies a signal, line 97 hits an unbound variable.
- I didn't check whether anything reads `raw` between the commit in the view and the worker, such as the UI list, the Slack message or plugins. Those readers would see unmasked data.

I changed no code. If you want the gap closed, the fix is to call `redact_raw` in `create_instance` before the JSON round trip. The flow's call can then stay as a safety net.

----- next turn -----

Entity extraction is fixed: a JSONPath that matches several fields now produces an entity for each match again, and `tests/entity` passes (11 tests).

**Cause:** commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2 Sep 2025) changed `find_entities` in `src/dispatch/entity/service.py`. It sliced the match list to `jpath.find(signal_instance.raw)[:1]` on the false assumption that a JSONPath names a single field. Wildcard and recursive paths such as `$..ip` match many fields, so every match after the first was dropped.

**Fix:** I removed the `[:1]` slice and its comment, so the line is back to `matches = jpath.find(signal_instance.raw)`. I didn't change any tests, and nothing is committed.

The same commit's "perf" intent is gone with this. If speed matters here, a safe option would be to cache the compiled JSONPath, but I haven't looked at whether that's worthwhile.

----- next turn -----

Masked values no longer become entities, and `tests/entity` and `tests/signal` pass (45 passed, 1 skipped).

**Why unrelated instances were grouped.** `signal_instance_create_flow` masks the payload with `redact_raw` and then extracts entities from it. The session token's JSONPath therefore matched `"[REDACTED]"`, which is the same string for every instance. `find_entities` turned it into one shared entity. The signal's deduplication filter matches instances that share an entity, so unrelated instances ended up in one case.

**Fix.** In `src/dispatch/entity/service.py`, the JSONPath loop in `find_entities` now skips any match whose value equals `MASK`, imported from `dispatch.signal.redaction`.
- This is the only place in `src/` that extracts entities from a payload. The `regular_expression` field is compiled but never applied to the payload, so I changed nothing for regexes.
- The masking itself is untouched.
- The check is an exact match on `"[REDACTED]"`, so a key you add to `SIGNAL_REDACTED_RAW_FIELDS` is covered too, since it masks to the same value.
- A payload that genuinely contains the literal text `[REDACTED]` also yields no entity.

**Tests.** I added `tests/entity/test_entity_redaction.py` and left the existing tests alone.
- One test runs two instances that differ only in the masked token and checks that they get no shared entity.
- The other checks that a masked match and a visible match under one wildcard path give only the visible entity.
- Both tests fail with the source fix stashed.

Instances already in the database were extracted before this fix. Their `[REDACTED]` entities and the cases they grouped together are not cleaned up. Nothing is committed.

----- next turn -----

Here is the recap for the weekly report. Nothing from today is committed.

## Investigation 1: permissions and visibility in the case and incident APIs

**Unguarded routes.** I listed every POST/PUT/PATCH/DELETE route without a `PermissionsDependency`. There were five. They are:
- `case.create_case`
- `case.create_case_channel`
- `case.create_case_resources`
- `incident.create_incident`
- `incident.delete_custom_event`

**Open by design:** `create_case` and `create_incident`, because anyone may report a case or incident.

**Regression:** `incident.delete_custom_event`. Commit `28c21e1e` ("refactor(incident): tidy custom event routes") removed its `IncidentEventPermission` check.
- I restored the check.
- I added `tests/incident/test_incident_views.py`, which fails if the check goes missing again.

**Left open:** `case.create_case_channel` and `case.create_case_resources` appear never to have had a check. They look like a design gap rather than a regression, so I left them. The incident equivalent, `create_incident_resources`, uses `IncidentViewPermission`. Whether the case routes should be guarded is a policy decision for you.

**Restricted cases visible to non-participants:** commit `42699ebc` ("refactor(database): flatten the restricted case filter") broke `restricted_case_filter` in `src/dispatch/database/service.py`. It split the `restricted and email == user` condition into separate `or_` branches, so every restricted case matched. I restored the `and_` grouping. I changed no existing tests, and I did not add a regression test for this one.

## Investigation 2: signal instances, masking and entities

**Flow** for `POST /signals/instances`:
1. The view stores the instance and commits it.
2. A worker (`dispatch signals process`) later picks it up and masks the payload.
3. The worker extracts entities, then runs the snooze and dedup filters.
4. Instances that pass the filters open a case, unless the signal is a canary or has case creation off.

**Masking:** `dispatch.signal.redaction.redact_raw` does it, replacing values with `[REDACTED]`.
- Keys match case-insensitively and exactly, at any depth.
- The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.
- The `SIGNAL_REDACTED_RAW_FIELDS` environment variable overrides the list.

**Unmasked payload in the database:** yes. `create_instance` stores the raw payload as sent and the view commits it. The worker masks it later, and if the worker fails before its first commit, the row stays unmasked. I recommended calling `redact_raw` inside `create_instance`, but I made no change for that.

**Entity extraction:** commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") sliced matches to `[:1]`, so a JSONPath matching several fields produced only one entity. I removed the slice, and `tests/entity` passes.

**Wrongly grouped GitHub token cases:** the session-token JSONPath matched the masked value `[REDACTED]`. It became one entity shared by every instance, and the dedup filter grouped them on it.
- `find_entities` now skips masked values.
- I added `tests/entity/test_entity_redaction.py`, which fails without the fix.
- Entities and cases created before the fix are not cleaned up.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1eb965d5e45696d84a22063c0ebf258618
VISIBILITY_BUG: 42699ebc7cdb4d95cd7c7163b2d99763b98a8289
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95