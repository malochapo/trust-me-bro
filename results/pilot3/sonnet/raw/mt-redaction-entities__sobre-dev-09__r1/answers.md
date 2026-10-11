**Short answer:** Yes. The unmasked payload is written to the database. Masking only happens later, in an asynchronous worker, so there is a window where the raw secrets are stored in plaintext.

## Trace

1. **API, `create_signal_instance`** (`signal/views.py:70`, `POST /instances`)
   - It resolves the project. It then finds the signal definition by `externalId` or `variant` in `raw`, falls back to the project's default, and returns 404 if there is none.
   - It calls `signal_service.create_instance(...)`, then `db_session.commit()` (`views.py:114-117`). A duplicate id raises `IntegrityError`, which becomes a 409.
   - It does not call the flow. `background_tasks` is accepted but unused. The response returns right after the commit.

2. **`signal_service.create_instance`** (`signal/service.py:650`)
   - It builds `SignalInstance(raw=json.loads(json.dumps(signal_instance_in.raw.copy())), ...)` and calls `db_session.add(...)`. The `json` round trip only converts dates. **No redaction happens here.**
   - If `raw["id"]` is set, it is used as the primary key. A non-UUID id gives a 400.

3. **Worker pickup**
   - Instances that have no `filter_action` and no `case_id` are picked up later. Two paths do this:
     - `signal/flows.py:~380-420`: `process_organization_signals` and `process_signal_batch`.
     - The CLI loop at `cli.py:~985-1010`.
   - Both call `signal_instance_create_flow` and commit after each instance.

4. **`signal_instance_create_flow`** (`signal/flows.py:46`)
   - **Masking:** line 60, `signal_instance.raw = redact_raw(signal_instance.raw)`. The comment there says it runs before entity extraction.
   - It then collects entity types (the signal's own plus the `all`-scoped ones) and runs `entity_service.find_entities`, which reads the now-redacted `raw`. It commits.
   - `signal_service.filter_signal` applies snooze and dedup rules.
     - If an action fires, it logs, updates the Slack signal message if a case and conversation exist, and returns. This is the filtered-out path.
   - If the instance is a canary, or `signal.create_case` is false, it returns without a case.
   - Otherwise it resolves case type, priority, severity, oncall assignee and conversation target, then calls `case_service.create`, sets `signal_instance.case`, and commits.
   - After that it runs `case_new_create_flow`, signal engagements if any, and workflows.

## The masking function

- **Function:** `redact_raw` in `signal/redaction.py:10`. The recursive helper is `_redact`.
- **Behaviour:** it returns a copy in which each matching key's value is replaced with `"[REDACTED]"`.
  - Matching is case-insensitive.
  - It applies at any depth, through dicts and lists.
  - Non-dict, non-list values are returned unchanged.
- **Default keys:** `password`, `secret`, `api_key`, `session_token`, `authorization`. They come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which the env var of the same name can override. Matching is on the exact key name, not a substring, so `client_secret`, `apiKey` and `token` are not masked by default.

## Is the unmasked payload ever written to the database?

Yes, in two places:

- **The API commit.** `views.py:114-117` commits the instance with the original `raw`, before any redaction.
- **Scheduler and CLI creation.** `create_signal_instance` in `signal/flows.py` (~line 296) also persists `raw=signal_instance_data` unredacted, with no `redact_raw` call.

Redaction only takes effect when the worker later runs the flow and commits (line 60, with the commit at line ~72). Until then the secrets sit in `signal_instance.raw`. This is also true if the worker is slow, if the flow raises before the commit, or if the flow is never run for that instance.

Other exposure:
- The API response returns the `SignalInstanceRead` of the unredacted instance.
- Anything that reads the instance between the commit and the worker run sees the secrets.

The fix would be to apply `redact_raw` in `signal_service.create_instance`, before `SignalInstance(...)` is built. That would cover both the API and scheduler paths. I haven't changed any code.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") caused it. It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`, so only the first match of each JSONPath became an entity.

I reverted that line to `matches = jpath.find(signal_instance.raw)` and removed the comment that justified truncating. `python -m pytest tests/entity` now gives 11 passed. I didn't change any tests, and I haven't committed the fix.

----- next turn -----

The grouping happens because masking runs before entity extraction. In `signal_instance_create_flow` (`signal/flows.py:60`), `redact_raw` replaces the session token with `"[REDACTED]"`. `find_entities` then reads that masked payload. Every instance of "GitHub: Personal access token exposed" therefore gets an entity with the value `[REDACTED]`. The deduplication filter on that entity type then sees them all as the same entity and groups them into one case.

**Fix:** in `src/dispatch/entity/service.py`, the JSONPath loop in `find_entities` now skips any match whose value equals `MASK` (imported from `dispatch.signal.redaction`). I left the masking itself as it was. That loop is the only place in the codebase that extracts entities from a payload. The `regular_expression` is compiled but never used for extraction.

**Test:** I added `test_find_entities_skips_masked_values` to `tests/entity/test_entity_service.py`. It redacts a payload, then checks that an entity type pointing at `session_token` produces nothing while one pointing at `user.name` still yields `alice`. `python -m pytest tests/entity tests/signal` gives 44 passed and 1 skipped. I didn't run the rest of the suite, and nothing is committed.

**Side effects:**
- Instances that used to be grouped on `[REDACTED]` will now have no entity for that field, so a dedup filter on it no longer groups them. Those instances then follow the normal case-creation path.
- A payload whose real value is literally `[REDACTED]` is also skipped.
- Only exact matches on `[REDACTED]` are caught. Masking by key name still misses keys like `client_secret`, so those values can still become entities.

----- next turn -----

## Recap

**Request path.** `POST /api/v1/{organization}/signals/instances` (`create_signal_instance`, `signal/views.py:70`) finds the signal definition. It calls `signal_service.create_instance`, then commits and returns. A worker later runs `signal_instance_create_flow` (`signal/flows.py:46`) on instances that have no `filter_action` and no `case_id`. The flow does the following:
- It masks `raw` with `redact_raw`.
- It extracts entities.
- It applies filters (snooze, dedup).
- It either returns, for filtered or canary instances and signals that don't create cases, or creates a case.

**Masking.** `redact_raw` in `signal/redaction.py` replaces the value of each matching key with `[REDACTED]`. Matching is on the exact key name, case-insensitive, at any depth. The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`. The `SIGNAL_REDACTED_RAW_FIELDS` setting can override them. Keys like `client_secret` or `apiKey` are not masked.

**Unmasked data is stored.** The API commit in `views.py` persists the original `raw`, and so does the scheduler path (`create_signal_instance` in `signal/flows.py`). Redaction only happens later in the worker. Secrets sit in plaintext in the database until then, and they are also returned in the API response. The suggested fix is to redact inside `signal_service.create_instance`. I haven't made that change.

**Entity extraction regression.** Commit `beb60cc4` added `[:1]` to the JSONPath `find` call in `entity/service.py`, so only the first match became an entity. I reverted that line, and `tests/entity` passes again.

**Masked values becoming entities.** Masking runs before extraction, so a masked session token became the entity `[REDACTED]` on every instance. The dedup filter then grouped unrelated GitHub token instances into one case. `find_entities` now skips values equal to `[REDACTED]`. I added `test_find_entities_skips_masked_values`, and `tests/entity` plus `tests/signal` give 44 passed and 1 skipped. The fixes are uncommitted.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4