Yes, the unmasked payload is written to the database. The API commits the raw payload as sent, and the masking happens later in a separate process.

**Trace of `POST /api/v1/{organization}/signals/instances`**

1. **View** (`signal/views.py:72`, `create_signal_instance`). It resolves the project. It then finds the signal definition by `externalId` or `variant` in `raw`, falling back to the project's default definition. If none exists it returns 404.
2. **Instance creation** (`signal/service.py:650`, `create_instance`). It builds a `SignalInstance`, copying `raw` as sent. It only drops `oncall_service` and round-trips the payload through JSON (`service.py:661-680`). It resolves the case priority, case type and oncall service, then calls `db_session.add`. If `raw["id"]` is set, it becomes the primary key. An invalid UUID gives a 400.
3. **Commit** (`views.py:~112`). The view calls `db_session.commit()`. A duplicate id gives a 409 (`IntegrityError`). The view then returns the instance. `background_tasks` is accepted as a parameter but never used, so the API does not run the processing flow.
4. **Asynchronous processing.** `signal_instance_create_flow` (`signal/flows.py:46`) is called from two places:
   - the scheduler loop through `process_signal_batch` and `process_organization_signals` (around `flows.py:380-420`);
   - the CLI at `cli.py:1004`.
   
   Both pick instances where `filter_action IS NULL` and `case_id IS NULL`, oldest first, and process them one at a time with a commit after each.
5. **Inside the flow:**
   1. **Masking:** `signal_instance.raw = redact_raw(signal_instance.raw)` at `flows.py:60`.
   2. **Entity extraction:** entity types from the signal definition plus those with `all` scope are run over the payload (`entity_service.find_entities`), then committed.
   3. **Filtering:** `signal_service.filter_signal` (`service.py:866`) applies snooze and dedup/filter rules. If it returns true, the instance is stored with its `filter_action`, the Slack signal message is updated if it was deduplicated into an existing case, and the flow returns. No new case is opened.
   4. **Early returns:** canary instances, and signals with `create_case` false, are stored and the flow returns.
   5. **Case creation:** otherwise the flow picks case type, priority, oncall service and conversation target, with the instance's own values first, then the signal's, then the case type's. It then creates the case.

**Where masking happens**
- **Function:** `redact_raw` in `signal/redaction.py:10`, with the recursive helper `_redact`.
- **Matching:** it returns a copy in which any key whose name is in the list has its value replaced with `"[REDACTED]"`. Matching is case-insensitive, applies at any depth, and goes through dicts and lists.
- **Default keys:** `password`, `secret`, `api_key`, `session_token`, `authorization`. These come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, a comma-separated environment variable that overrides the default.
- **Limits:** only exact key names match, so `api-key` or `apiKey` would not be masked. Sensitive values in string values or under other key names are untouched.

**Is the unmasked payload ever written to the database?**
- **Yes.** The API path commits the raw payload as sent (steps 2–3). It stays that way until the scheduler or CLI picks the instance up. The API response, `SignalInstanceRead`, is also built from the unredacted instance.
- **Redaction is not guaranteed to run.** If the flow throws before `flows.py:60`, or the scheduler is down or lagging, the instance keeps its sensitive values. The batch limit is 500 per pass in the CLI.
- **Dedup edge case:** `service.py:730-737` has an update path that also stores the raw payload without masking. I did not trace which callers reach it.
- **Fix, if you want one:** call `redact_raw` in `service.create_instance`, or in the view before creating the instance. I haven't changed any code.

----- next turn -----

The regression came from commit `beb60cc4` ("perf(entity): stop at the first JSONPath match"). It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`. That cut every JSONPath down to its first match, so an entity type matching several fields produced only one entity.

I restored `matches = jpath.find(signal_instance.raw)` and removed the comment that justified the slice. I didn't touch the tests. `python -m pytest tests/entity` now passes, 11 tests. I only ran that directory, not the full suite.

I haven't committed anything.

----- next turn -----

Unrelated instances were grouped because masking turned their session tokens into the same string. The fix is in, with a new test, and `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**Cause.** Before extracting entities, `signal_instance_create_flow` runs `redact_raw` on the payload, which replaces every `session_token` value with `"[REDACTED]"`. The JSONPath for the session token then matched that string. Every instance got the same entity value, `[REDACTED]`, and the dedup filter on that entity type treated them all as the same alert.

**Other callers.** `find_entities` is also called from `entity_type/service.py:95` and `entity_type/flows.py:29`, which re-extract entities from instances already stored. Those instances can still hold unmasked values, because the API stores the raw payload before masking, as I found earlier. In that case, a token would have become an entity holding the real secret.

**Fix.** The change is in `find_entities` in `src/dispatch/entity/service.py`, so every caller gets it:
- It now searches a redacted copy of the payload, using the existing `redact_raw`.
- It skips any match whose value equals `MASK`.

The masking in `redact_raw` is unchanged.

**Test.** `test_find_entities_skips_masked_values` in `tests/entity/test_entity_service.py` covers a top-level `session_token`, a nested `SESSION_TOKEN` inside a list, and a normal `user` field. It checks both an already-redacted payload and an unredacted one. In both cases only `alice` becomes an entity.

I haven't committed anything.

----- next turn -----

## Recap

**Flow.** `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `signal/views.py`.
1. The view finds the signal definition, using the default one if needed, and returns 404 if none exists.
2. `signal_service.create_instance` builds the instance from the payload as sent and the view commits it. A duplicate id returns 409.
3. The API does not process the instance. The scheduler (or the CLI) picks up instances with no `filter_action` and no case, and runs `signal_instance_create_flow`.
4. That flow masks the payload with `redact_raw` (`flows.py:60`) and extracts entities.
5. `filter_signal` then applies snooze, dedup and filter rules. A filtered instance is stored and the flow stops. Canary instances and signals with `create_case` off are also stored and stop there.
6. Otherwise a case is created.

**Masking.** `redact_raw` replaces the value of any matching key with `"[REDACTED]"`. Matching is case-insensitive, at any depth, through dicts and lists. Only exact key names match, so `api-key` and `apiKey` are not masked. The defaults come from `SIGNAL_REDACTED_RAW_FIELDS` and can be overridden by environment variable.

**Unmasked in the database.** Yes. The API commits the raw payload before the flow masks it. The unmasked payload stays in the database until the scheduler or CLI processes the instance. If that never happens, it stays permanently. The API response is also built from the unmasked instance. `service.py:730-737` has an update path that stores the raw payload unmasked. I did not trace its callers.

**Entity extraction bugs.**
- **First-match bug:** commit `beb60cc4` sliced JSONPath matches to the first one. I removed the slice.
- **Dedup grouping bug:** extraction ran on masked payloads, so every session token became the entity `[REDACTED]` and unrelated instances were deduplicated together. `find_entities` now searches a redacted copy and skips masked values. A test covers both cases.

Neither fix is committed.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95