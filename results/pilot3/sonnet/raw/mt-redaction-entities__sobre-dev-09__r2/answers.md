I traced the full path, and the unmasked payload is written to the database. Redaction only runs later, in a separate worker. I changed nothing.

**1. API request** (`signal/views.py:70`, `create_signal_instance`)
- It resolves the project and the signal definition, by `externalId` or `variant` in `raw` or by the default definition. If none is found it returns 404.
- It calls `signal_service.create_instance` (`signal/service.py:650`) and then `db_session.commit()` (`views.py:119`). A duplicate id returns 409.
- `create_instance` copies `raw` through `json.loads(json.dumps(...))` and builds the `SignalInstance`. It applies the priority, case type and oncall service, then does `db_session.add`.
- **No redaction happens here.** The view takes a `background_tasks` argument but never uses it, and it doesn't start the create flow. It returns the stored instance.

**2. Asynchronous pickup** (`cli.py`, around lines 960–1015, the signals consume loop)
- A long-running loop goes through each organization. It selects up to 500 instances where `filter_action IS NULL` and `case_id IS NULL`, oldest first.
- For each one it calls `signal_flows.signal_instance_create_flow` and commits. On an exception it rolls back and continues. This is the only caller of the flow.

**3. `signal_instance_create_flow`** (`signal/flows.py:48`)
- **Masking happens here, at `flows.py:60`.** The line is `signal_instance.raw = redact_raw(signal_instance.raw)`, and it runs before anything else.
- Entities are then extracted from the now-masked payload (`entity_service.find_entities`) and committed.
- `signal_service.filter_signal` applies the snooze filter, then the dedup filter. If either acts, the flow logs it, optionally updates the Slack signal message, and returns. No case is opened.
- If the instance is a canary, or `signal.create_case` is false, the flow returns with the instance stored and no case.
- Otherwise it resolves case type, priority, oncall assignee and conversation target. It then calls `case_service.create`, sets `signal_instance.case`, commits, and continues into the case flow.

**Masking function:** `redact_raw` in `signal/redaction.py:10`, with the recursive helper `_redact`.
- It returns a copy of the payload.
- It matches key names, not values.
- Matching is case-insensitive and applies at any depth, inside dicts and lists.
- A matched key's value is replaced with `"[REDACTED]"`.

**Default keys** (`config.py:98`, `SIGNAL_REDACTED_RAW_FIELDS`): `password`, `secret`, `api_key`, `session_token`, `authorization`. The `SIGNAL_REDACTED_RAW_FIELDS` environment variable overrides them with a comma-separated list.

**Is the unmasked payload written to the database? Yes.**
- The API commits the raw payload at `views.py:119`, before any redaction.
- It stays unmasked in the `raw` column until the worker reaches the instance and commits the masked copy. That commit happens at the entity commit (`flows.py:~71`) or the worker's per-instance commit.
- If the worker is down or backlogged, the unmasked payload stays stored indefinitely. If the flow throws before the commit, the rollback leaves the unmasked version in place.
- Unmasked values are also returned in the POST response (`SignalInstanceRead`).

**Other gaps I noticed**
- `signal_service.update_instance` (`service.py:~730`) overwrites `raw` without redaction.
- The scheduler helper `signal/flows.py:create_signal_instance` goes through `create_instance` and has no redaction of its own.
- Only key names are matched, so a secret under a key not in the list, or inside a string value, is stored as sent.

If you want the masking moved into the API path, `create_instance` is the natural place, because both entry points go through it.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") caused it. It changed `find_entities` in `src/dispatch/entity/service.py` to `matches = jpath.find(signal_instance.raw)[:1]`. That kept only the first match for each entity type.

I reverted that line to `matches = jpath.find(signal_instance.raw)`, which is what the file had before the commit. I didn't touch the tests. `python -m pytest tests/entity` now passes (11 passed). I didn't run the rest of the suite.

The change is uncommitted in the working tree.

----- next turn -----

Unrelated "GitHub: Personal access token exposed" instances were grouped because redaction runs before entity extraction. I fixed it so a masked value never becomes an entity. `python -m pytest tests/entity tests/signal` gives 44 passed and 1 skipped. I didn't run the full suite.

**Cause:** `signal_instance_create_flow` calls `redact_raw` at `signal/flows.py:60`, which turns the `session_token` value into the literal `"[REDACTED]"`. The entity type's JSONPath then matched that placeholder, so every instance got an entity with the same value. The deduplication filter on that entity type saw identical entities and put the instances in one case. This follows from the masking and fits what the analysts report. I didn't reproduce it end to end with a real signal and filter.

**Fix:** `src/dispatch/entity/service.py` now imports `MASK` from `dispatch.signal.redaction`. The JSONPath loop in `find_entities` skips any match whose value equals `MASK`. `find_entities` is the only place entities are extracted from a payload, so this covers every caller. The masking itself is unchanged.

**Test:** `test_find_entities_skips_masked_values` in `tests/entity/test_entity_service.py` is new. It redacts a payload that has `session_token`, a nested `Password` and a normal `asset[*].id`. It asserts that only the asset entity is created. I didn't edit any existing tests.

Both changes, together with the earlier revert of the first-match slice, are uncommitted in the working tree.

A genuine payload value that is literally `"[REDACTED]"` is also skipped.

----- next turn -----

**Recap**

- **Request path:** `POST /api/v1/{organization}/signals/instances` (`signal/views.py:70`) resolves the signal definition and calls `signal_service.create_instance`. It then commits the instance with its raw payload exactly as received.
- **Worker:** the `signals consume` loop in `cli.py` later picks up instances that have no `filter_action` and no `case_id`. It runs `signal_instance_create_flow` on each one.
- **Masking:** the first thing the flow does is `signal_instance.raw = redact_raw(signal_instance.raw)` (`signal/flows.py:60`). `redact_raw` matches key names case-insensitively at any depth and replaces their values with `"[REDACTED]"`.
- **What happens next:** entities are extracted, then snooze and dedup filters run. An instance ends in one of these ways:
  - filtered out (snoozed or deduplicated);
  - stored as a canary;
  - stored with no case because the signal has `create_case` off;
  - turned into a case.
- **Database exposure:** the API commits the unmasked payload before any masking runs. It stays in the database until the worker commits the masked copy. If the worker is down or the flow fails before its commit, it stays unmasked indefinitely. `update_instance` and the scheduler's `create_signal_instance` helper never redact.
- **Extraction bug:** commit `beb60cc4` added `[:1]` to the JSONPath matches in `find_entities`, so only the first match per entity type was kept. I reverted that line.
- **Grouping bug:** extraction ran on already-masked payloads, so every instance got an entity with the value `"[REDACTED]"`. The dedup filter then grouped unrelated instances. `find_entities` now skips masked values, and `test_find_entities_skips_masked_values` covers it.
- **Status:** the fixes and the new test are uncommitted. `tests/entity` and `tests/signal` pass.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4