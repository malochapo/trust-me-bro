Five routes that change data have no `PermissionsDependency` in their route definition. I read the decorators in both files. I didn't trace the handler bodies or any router-level dependencies.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case`, line 162.
2. `POST /{case_id}/resources/conversation` → `create_case_channel`, line 236.
3. `POST /{case_id}/resources` → `create_case_resources`, line 260.

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident`, line 117.
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event`, line 503. This one stands out because its sibling event routes (create, update and export) all require `IncidentEventPermission`.

All other POST, PUT, PATCH and DELETE routes in both files declare a `PermissionsDependency`.

The two `POST ""` create routes may be intentionally open to any authenticated user. I haven't checked whether the API router applies authentication to them. I also haven't checked whether the two case resource routes get any check inside their handlers.

I haven't changed any code.

----- next turn -----

Yes, one of them is a regression: `DELETE /{incident_id}/event/{event_uuid}` (`delete_custom_event` in `src/dispatch/incident/views.py`). The new test passes with the fix and fails when the fix is reverted. I ran only that test, not the full suite.

**Where it went missing:** commit `28c21e1e`, "refactor(incident): tidy custom event routes", deleted the `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` line. The commit message calls it a refactor, but it dropped the authorization check. Before that commit, the other timeline event routes (create, update, export) were guarded the same way.

**The other two are original design, not regressions:** `create_case_channel` and `create_case_resources` have never had a permission dependency. They were added without one in `ced74f33` and `f08a22b3`. I left them alone. You may still want to decide whether they should require `CaseEditPermission`.

**Changes:**
- `src/dispatch/incident/views.py`: restored `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]` on the route.
- `tests/incident/test_incident_views.py` (new): `test_delete_custom_event_requires_event_permission` looks up the DELETE route on the incident router and asserts that `IncidentEventPermission` is among its declared permissions.

Nothing is committed.

----- next turn -----

The cause is in `restricted_case_filter` in `src/dispatch/database/service.py`, and I've fixed it. Commit `42699ebc`, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2025-09-02), introduced it. The tests in `tests/database`, `tests/case` and `tests/incident` pass with the fix (41 passed), and I didn't change any existing test.

**Cause:** the commit removed the `and_` around the restricted-case condition, so the filter became:

```
open  OR  restricted  OR  participant-email == user
```

The middle term matches every restricted case for any user who isn't an admin, owner or manager. The correct condition is `open OR (restricted AND participant-email == user)`. The incident filter right next to it still has the `and_`.

**Fix:** I put the `and_` back around the restricted and participant-email terms.

**Not part of this fix:**
- I didn't add a regression test for this one. The existing tests didn't catch it, so a test that creates a restricted case and checks what a non-participant can list would close that gap. I can write one if you want.
- Six tests in `tests/ai/test_ai_service.py` fail. They fail the same way with my changes stashed, so they predate this work and are unrelated.
- Nothing is committed. The working tree now holds this fix, the earlier incident permission fix and its new test.

----- next turn -----



----- next turn -----

Yes, the unmasked payload is written to the database. The API commits the raw payload as received, and masking only runs later, when a separate worker processes the instance. I changed no code.

## Trace of `POST /api/v1/{organization}/signals/instances`

1. **API handler** (`create_signal_instance`, `signal/views.py:70`). It resolves the project. It then looks for a signal definition by `externalId` or `variant` in the payload, and falls back to the project's default definition. If it finds none, it returns 404.
2. **Instance creation** (`signal_service.create_instance`, `signal/service.py:650`). It copies `raw` through a JSON round trip and builds the `SignalInstance`. If the payload has an `id`, that becomes the primary key, and a non-UUID `id` gives 400. It adds the instance to the session.
3. **Commit** (`signal/views.py:118`). This commits the instance and returns it. A duplicate `id` gives 409. The handler does not run the create flow. `BackgroundTasks` is a parameter but is never used.
4. **Worker pickup**. Two code paths pick up unprocessed instances: `process_organization_signals` / `process_signal_batch` in `signal/flows.py:~390`, and a loop in `cli.py:~1004`. Both select up to 500 instances with `filter_action IS NULL` and `case_id IS NULL`, oldest first. Both call `signal_instance_create_flow` and commit per instance.
5. **Create flow** (`signal_instance_create_flow`, `signal/flows.py:43`):
   - It masks `raw` (line 60).
   - It extracts entities from the masked payload and commits.
   - `filter_signal` applies snooze filters, then dedup filters. If neither matches, it sets `filter_action = none`.
   - **Filtered out:** if the instance was snoozed or deduplicated, it returns. If it was attached to an existing case with a conversation, it updates the Slack signal message.
   - **Stored only:** canary signals, and signals with `create_case` off, are stored and the flow returns.
   - **Case opened:** otherwise it builds a `CaseCreate` (`visibility=open`) and calls `case_service.create`. It sets `signal_instance.case`, commits, and goes on to the case-creation flow.

## Masking

- **Where:** `redact_raw` in `src/dispatch/signal/redaction.py`. Its only call site is `signal/flows.py:60`.
- **How it works:** it returns a copy of the payload with the value of every matching key replaced by `"[REDACTED]"`. Keys match case-insensitively, at any depth, inside dicts and lists. It matches key names only, never values. Non-dict, non-list values pass through unchanged.
- **Default keys:** `password`, `secret`, `api_key`, `session_token`, `authorization`. These come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which an environment variable can override with a comma-separated list. Matching is exact, so `client_secret`, `apiKey` and `access_token` are not masked by default.

## Is the unmasked payload written to the database?

Yes, in two ways:

- **Window before masking.** The commit in step 3 writes the raw payload exactly as sent. It stays that way until a worker runs the create flow. The worker runs on a loop with a 60-second delay (`LOOP_DELAY`), so the window is at least that long. It is longer if the worker is down or backlogged. During that time the plaintext is in the `raw` column and visible through `GET /signals/instances`.
- **Failed processing.** If the flow raises before the commit that follows line 60, the batch loop rolls back. The instance then keeps its unmasked `raw` and is retried on the next pass. It stays unmasked until a run succeeds.

Separately, `signal_service.update_instance` (`signal/service.py:737`) replaces `raw` without masking it. I found no caller of it, so it is only a latent risk.

The fix would be to call `redact_raw` in `create_instance` before the instance is built, or in the view before the first commit. If you want me to change that, say so.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, 2025-09-02) caused it. I've reverted its one-line change in `find_entities` in `src/dispatch/entity/service.py`. `python -m pytest tests/entity` now gives 11 passed.

The commit changed `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. That cut every JSONPath down to its first match. An entity type whose path matches several fields, such as `$..ip` or `$.items[*].host`, therefore produced only one entity. The fix is the original `matches = jpath.find(signal_instance.raw)`, with the commit's comment removed.

The commit's "perf" claim doesn't hold up. `find` already builds the full match list before the slice, so the slice saved no work and only dropped results.

I didn't change any tests. Nothing is committed. The working tree still holds the earlier incident permission fix, the `restricted_case_filter` fix and the new `tests/incident/` file.

----- next turn -----

Masked values can no longer become entities. That is what was grouping unrelated "GitHub: Personal access token exposed" instances into one case.

**Cause:** `signal_instance_create_flow` masks `raw` first, so the session token becomes the literal `"[REDACTED]"`. Entity extraction then ran the JSONPath on that masked payload. Every instance produced the same entity, `[REDACTED]`, and the deduplication filter on that entity type treated them all as duplicates and attached them to one case. Masking was not the bug.

**Fix:** `find_entities` in `src/dispatch/entity/service.py` is the only place entities are extracted from a payload. It now does two things:
- It skips any match whose value is the mask, so an already-masked payload gives no entity.
- It runs `redact_raw` on the payload itself before the JSONPath lookup. A caller that passes an unmasked payload therefore can't turn a real secret into an entity either.

I left `redaction.py` and the masking itself unchanged.

**Tests:** I added `tests/entity/test_entity_redaction.py`, one test for each of those two cases. Both fail without the fix and pass with it. `tests/entity` and `tests/signal` give 45 passed, 1 skipped. I changed no existing tests.

An entity type pointed at a sensitive field now never produces entities, so a deduplication filter on it has nothing to match. Unrelated instances will no longer be grouped, but that filter also stops deduplicating anything. If analysts need deduplication for that signal, the filter should use a different entity type, such as the repository or the token's owner.

Nothing is committed. The working tree still holds the earlier fixes: the incident permission check, the `restricted_case_filter` fix, the JSONPath first-match revert and the new test files.

----- next turn -----

## Recap

### Investigation 1: unprotected data-changing routes
- Before my changes, five POST/DELETE handlers in `src/dispatch/case/views.py` and `src/dispatch/incident/views.py` had no `PermissionsDependency`. I confirmed the list by re-parsing the committed (HEAD) versions of both files.
- `case.create_case` and `incident.create_incident` are open on purpose, because anyone may report a case or an incident.
- `incident.delete_custom_event` was a regression. Commit `28c21e1e` removed its `IncidentEventPermission` check. I restored the check and added `tests/incident/test_incident_views.py`. I confirmed the test passes with the fix and fails without it.
- `case.create_case_channel` and `case.create_case_resources` never had a check (commits `ced74f33` and `f08a22b3`). I left them as they were. They are still unprotected and need a decision from you.

### Investigation 2: restricted cases on the cases list
- Commit `42699ebc` flattened `restricted_case_filter` in `src/dispatch/database/service.py` into `open OR restricted OR participant-email`. That showed every restricted case to any user who isn't an admin, owner or manager.
- I restored `and_(restricted, participant-email)`. The `tests/database`, `tests/case` and `tests/incident` suites passed with 41 tests. I added no regression test for this one.
- Six tests in `tests/ai/test_ai_service.py` fail. They fail the same way without my changes, so they are unrelated.

### Signal instance trace and masking
- `redact_raw` in `dispatch.signal.redaction` does the masking. It is called only from `signal_instance_create_flow`. Commit `d2675cf4` introduced it.
- The default masked keys are `password,secret,api_key,session_token,authorization`. Matching is exact and case-insensitive, at any depth.
- The unmasked payload is written to the database. The API commits `raw` as received, and a background worker masks it later.

### Entity extraction bugs
- Commit `beb60cc4` made entity extraction keep only the first JSONPath match. I reverted that one-line change, and `tests/entity` passed.
- Entity extraction ran on the masked payload, so the GitHub token signal's session token became the entity `[REDACTED]`. That grouped unrelated instances under one case through the deduplication filter.
- `find_entities` now skips masked values, and it masks the payload itself before extraction. I added `tests/entity/test_entity_redaction.py`, and its two tests fail without the fix.

Nothing is committed. I changed no existing tests.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4