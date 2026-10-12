Six data-changing routes declare no `PermissionsDependency` in their route definition. I checked every POST, PUT, PATCH and DELETE decorator in both files.

**Case API (`src/dispatch/case/views.py`)**
1. `POST ""` → `create_case`, line 162.
2. `POST /{case_id}/resources/conversation` → `create_case_channel`, line 236.
3. `POST /{case_id}/resources` → `create_case_resources`, line 260.

**Incident API (`src/dispatch/incident/views.py`)**
4. `POST ""` → `create_incident`, line 117.
5. `DELETE /{incident_id}/event/{event_uuid}` → `delete_custom_event`, line 503. This is the only destructive one. Its case-API counterpart is protected by `CaseEventPermission`, so the incident version looks like an oversight.

That makes six in total, three per file. Every other mutating route in both files declares a `PermissionsDependency`.

I only looked at the route decorators. The router may be mounted with a dependency in `api.py`, or the function bodies may check permissions themselves. I haven't checked either, so these may not be fully open.

I haven't changed any code.

----- next turn -----

One of the five was a regression: the incident `DELETE /{incident_id}/event/{event_uuid}` route (`delete_custom_event`). I've restored its check and added a test. The test passes with the fix and fails without it.

**The regression**
- Commit `28c21e1e`, "refactor(incident): tidy custom event routes" (Sam Ortega, 2025-07-14), deleted one line from that route: `dependencies=[Depends(PermissionsDependency([IncidentEventPermission]))]`.
- The commit message calls it a tidy-up, but the diff removes the permission check and changes nothing else.
- The sibling routes for creating, updating and exporting custom events kept the check.

**The other two case routes were never protected**
- `create_case_channel` and `create_case_resources` have had no check since they were added, in `ced74f33` and `f08a22b3`. They are a design gap or oversight rather than a regression.
- I left them alone. You may still want to review them, since they let anyone trigger resource creation on any case.

**Changes**
- `src/dispatch/incident/views.py`: put the original `IncidentEventPermission` dependency back on `delete_custom_event`.
- `tests/incident/test_incident_event_views.py` (new): checks that the incident DELETE event route declares `IncidentEventPermission`.
- The test inspects the route definition rather than calling the endpoint. Calling the view function directly would skip the dependency, which is how the existing event tests work.
- I ran only the new test, not the full suite. I haven't committed anything.

----- next turn -----

I found the cause and fixed it. The change is uncommitted, and the existing tests in `tests/database` pass (25 passed) without any edits.

**Cause:** `restricted_case_filter` in `src/dispatch/database/service.py` (around line 833) applies to every role except admin, owner and manager. Its visibility condition had been flattened into one `or_` with three separate branches:
- `Case.visibility == open`
- `Case.visibility == restricted`, with no participant check
- `IndividualContact.email == current_user.email`

The second branch matched every restricted case for every user. The third matched any case the user takes part in. That is why the security team member saw restricted cases they aren't part of.

**Fix:** I put the `and_` back, so a restricted case only shows when the user's email matches a participant on it. This matches `restricted_incident_filter`, which was never changed.

**Introduced by:** commit `42699ebc`, "refactor(database): flatten the restricted case filter" (Sam Ortega, 2025-09-02). It is the same author and the same kind of "tidy-up" commit as `28c21e1e` from the earlier finding, which removed the incident delete permission check. The commit's own diff shows it changed behaviour, so it isn't a pure refactor. The `and_` was in place before it, from `7931a1e6` ("Respect restricted case visibility") through `b05613b5`.

I didn't add a regression test, since you said the existing ones are correct and shouldn't change. I can add a new test that creates a restricted case with no participation for a non-privileged user, if you want one.

----- next turn -----



----- next turn -----

Yes, the unmasked payload is written to the database. The masking runs later, in a separate worker step. Until that step runs, the stored `raw` column holds the original values, and so does the API response. I changed no code.

## The path of a signal instance

**1. `create_signal_instance`** (`src/dispatch/signal/views.py:70`)
- The route is `POST /instances`, rate-limited to 1000/minute.
- It resolves the project.
- If the payload names no signal, it looks the signal up by `raw["externalId"]` or `raw["variant"]`, then falls back to the project's default signal. If neither exists it returns 404.
- It calls `signal_service.create_instance(...)` and then `db_session.commit()`. A duplicate id raises `IntegrityError`, which becomes a 409.
- It returns the instance as `SignalInstanceRead`.
- `background_tasks` is declared as a parameter but never used, so the API does not start any processing.

**2. `signal_service.create_instance`** (`src/dispatch/signal/service.py:650`)
- It copies `raw` and runs it through `json.loads(json.dumps(...))`. This only turns date strings into JSON-safe values. It does not mask anything.
- It builds the `SignalInstance`. If `raw["id"]` exists, that becomes the primary key, and it must be a valid UUID or the route returns 400.
- It attaches the case type, priority and oncall service, then calls `db_session.add`.

**3. The worker picks it up.**
- `process_signal_batch` in `signal/flows.py` and the CLI loop (`cli.py:~1004`) both select instances where `filter_action IS NULL` and `case_id IS NULL`, oldest first, up to 500 per pass.
- Each instance goes through `signal_instance_create_flow`, followed by a commit.

**4. `signal_instance_create_flow`** (`signal/flows.py:46`)
- It first runs `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60). Masking happens before entity extraction and before any filtering.
- It then collects entity types from the signal plus the global ones, runs `entity_service.find_entities` and commits.
- `signal_service.filter_signal` runs next. If a filter acted (snooze or deduplicate), the flow logs it, may update the Slack signal message for an existing case, and returns. The instance is filtered out.
- Canary signals, and signals with `create_case` off, are stored and the flow returns.
- Otherwise it resolves the case type, priority, oncall service and conversation target. Instance values win over signal values, which win over case type values. It then creates the case.

## The masking

- **Where:** `src/dispatch/signal/redaction.py`, added in commit `d2675cf4` ("mask sensitive raw fields before processing").
- **Function:** `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)`, which calls the private `_redact`.
- **Behaviour:**
  - It returns a copy of the payload.
  - Keys are compared case-insensitively, after trimming whitespace.
  - It recurses through dicts and lists at any depth.
  - A matching key has its whole value replaced by `"[REDACTED]"`, including nested objects.
  - Values that are neither dicts nor lists pass through unchanged.
- **Default keys** (`src/dispatch/config.py:98`, overridable with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable, comma-separated): `password`, `secret`, `api_key`, `session_token`, `authorization`.
- **Matching is exact on the key name.** Keys such as `access_token`, `apiKey`, `x-api-key` or `client_secret` are not masked by default.

## Is the unmasked payload written to the database?

- **At creation:** yes. `create_instance` adds the unmasked `raw` and the view commits it. The 200 response (`SignalInstanceRead`) is built from that same instance.
- **Window:** the unmasked values stay in the `raw` JSONB column until the worker processes the instance. The worker runs about once a minute (`LOOP_DELAY = 60`), but a backlog or a worker outage lengthens it.
- **After the flow:** the masked value replaces `raw` and is committed with the next commit (the one after entity extraction, or the worker's per-instance commit).
- **Failures:** if the flow raises, the worker rolls back, so the instance keeps its unmasked `raw` and is retried on the next pass.
- **Other copies:** database backups, replicas or logs taken during the window would also contain the unmasked values.

## Fix, if you want one

The simplest fix is to call `redact_raw` in `create_instance` before the `SignalInstance` is built. That would mask at write time and in the API response. The catch is that entity extraction and filters read `raw`, so they would then see `[REDACTED]` for those keys. That is probably fine, but it changes behaviour.

I did not check whether `raw` is used for anything else after the flow, such as the Slack message or case description.

I also did not look for a test of `redact_raw` itself. The only tests that mention the flow are in `tests/signal/test_signal_flow.py`.

## Correction to my first answer

In my turn-1 answer I said "six in total, three per file". The list had five routes: three in the case views and two in the incident views.

----- next turn -----

The cause was commit `beb60cc4`, "perf(entity): stop at the first JSONPath match" (Sam Ortega, 2025-09-02). I've reverted its code change in the working tree, and `python -m pytest tests/entity` now passes (11 passed). I didn't touch any tests and haven't committed.

**What it did:** in `find_entities` in `src/dispatch/entity/service.py`, it changed `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. Entity types whose JSONPath matched several fields, for example a wildcard like `$.users[*].email`, then produced only one entity. The commit message called this a performance change, but it changes behaviour. Slicing after `find` also saves almost nothing, because `find` has already computed every match.

**Fix:** I removed the slice and its comment, so every string match becomes an entity again. The code is back to how it was before that commit.

----- next turn -----

Unrelated "GitHub: Personal access token exposed" instances were grouped because their masked token became a shared entity. It is fixed, and the entity and signal tests pass (45 passed, 1 skipped). Nothing is committed.

**Cause:** this is the interaction of two things I described earlier.
- `signal_instance_create_flow` replaces the value of `session_token` (a default masked key) with `"[REDACTED]"` before it extracts entities.
- `find_entities` then ran the entity type's JSONPath over the masked payload and created an entity whose value is the literal string `[REDACTED]`. Entities are matched by value, so every instance of that signal got the same entity.
- The deduplication filter on that entity type saw "same entity" and merged unrelated instances into one case.

**Fix:** in `src/dispatch/entity/service.py`, `find_entities` now skips any match whose value equals `MASK` (imported from `dispatch.signal.redaction`). The masking itself is unchanged.

**Why this covers every extraction path:** `find_entities` is the only place entities are extracted from a payload. All three callers go through it:
- `signal/flows.py`
- `entity_type/flows.py`
- `entity_type/service.py`, which re-extracts from instances that are already masked in the database.

The regular-expression branch isn't implemented in that function, so nothing else needed guarding.

**Tests:** I added `tests/entity/test_entity_masked_values.py`, leaving the existing tests alone. It has two cases:
- A `session_token` value passed through `redact_raw` yields no entity.
- A wildcard path over `[MASK, "visible"]` yields only `visible`.

Both fail without the fix.

A masked value could still be a legitimate value if a payload literally contained the text `[REDACTED]`. It would be skipped too, which seems acceptable.

----- next turn -----

## Recap

**1. Permission review (case and incident APIs)**
- Five data-changing routes had no `PermissionsDependency` when I started. The `create_case` and `create_incident` routes are open on purpose, because anyone may report. The two case resource routes (`create_case_channel` and `create_case_resources`) never had a check, so I reported them as an oversight and left them alone.
- The only regression was `incident.delete_custom_event`. Commit `28c21e1e` removed its `IncidentEventPermission`. I restored the check and added `tests/incident/test_incident_event_views.py`, which fails if the check goes missing.
- My first answer said "six in total", which was a miscount. The list was five routes.

**2. Restricted cases on the cases list**
- Commit `42699ebc` flattened `restricted_case_filter` in `src/dispatch/database/service.py` into one `or_`. That made every restricted case visible to non-privileged users.
- I restored the `and_` of "restricted and the user is a participant". The existing tests were not changed and pass. I did not add a regression test for this one.

**3. Signal instance flow and masking**
- Masking is done by `dispatch.signal.redaction.redact_raw`, called from `signal_instance_create_flow`. It was introduced by commit `d2675cf4`.
- It runs in the worker step, not in the API route. `POST /instances` commits the unmasked `raw` first, so the unmasked payload is written to the database until the worker processes the instance. The 200 response also carries the unmasked payload.
- The default masked keys are `password`, `secret`, `api_key`, `session_token` and `authorization`, matched exactly and case-insensitively.

**4. Entity extraction**
- Commit `beb60cc4` ("stop at the first JSONPath match") made `find_entities` keep only the first match. I reverted it, and `tests/entity` passes.

**5. Masked values grouped into one case**
- The masked token (`[REDACTED]`) became a shared entity, so the deduplication filter merged unrelated instances. `find_entities` now skips masked values. The masking itself is unchanged.
- I added `tests/entity/test_entity_masked_values.py`.

None of the changes are committed.

UNPROTECTED_AT_START: case.create_case, case.create_case_channel, case.create_case_resources, incident.create_incident, incident.delete_custom_event
RESTORED: incident.delete_custom_event
REMOVED_BY: 28c21e1e
VISIBILITY_BUG: 42699ebc
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4