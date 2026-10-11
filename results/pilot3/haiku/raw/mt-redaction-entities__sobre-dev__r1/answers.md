Short answer: masking happens in the batch flow, not in the API handler, and the API handler commits the unmasked payload to the database before masking runs. So yes, the unmasked payload is written to the database.

## Path of a POST to `/api/v1/{org}/signals/instances`

1. **Route:** `src/dispatch/signal/views.py:70-72` (`create_signal_instance`, rate-limited to 1000/min). It resolves the project, finds the signal definition by external ID or variant, falls back to the default definition, and returns 404 if none exists.
2. **Create:** `signal_service.create_instance` (`src/dispatch/signal/service.py:650`) builds the `SignalInstance` with `raw=json.loads(json.dumps(...))`, a copy of the payload with no masking. It adds the row to the session.
3. **Commit:** `views.py:120` runs `db_session.commit()`. The row, including the unmasked `raw` (a JSONB column, `models.py:239`), is now in the database. The handler then returns the instance.
4. **Processing happens later, not in the request.** The API never calls `signal_instance_create_flow`. A long-running loop, `main_processing_loop` in `src/dispatch/signal/flows.py` (around line 440), wakes every `LOOP_DELAY` seconds. It calls `get_unprocessed_signal_instance_ids` (`service.py:901`), which selects rows with no `filter_action` and no `case_id`, then calls `process_signal_batch` (`flows.py:386`). The CLI path at `cli.py:1004` also calls the flow.
5. **Flow:** `signal_instance_create_flow` (`flows.py:46`):
   - Line 60: `signal_instance.raw = redact_raw(signal_instance.raw)`. This is the masking step.
   - Lines 63-75: entity extraction runs on the redacted `raw`. If entities were found, the session commits at line 75.
   - Lines 78-100: `filter_signal` runs (snooze, dedup, and other filters). If a filter applies, the flow returns here, and the instance is marked filtered or deduplicated (`service.py:866`, which commits at line 896).
   - Lines 103-107: canary and `create_case=False` signals return without a case.
   - Otherwise a case is created (around `flows.py:189`), `signal_instance.case = case`, and the session commits.

## Where masking happens

- **Function:** `redact_raw` in `src/dispatch/signal/redaction.py:10`, with the recursive helper `_redact` at line 20.
- **Behavior:** it returns a copy. Keys are compared case-insensitively, at any depth, inside dicts and lists. Matching values become the string `"[REDACTED]"` (`MASK`, line 7). Other values are returned unchanged.
- **Default keys:** `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98-102`, overridable by the environment variable of the same name. The default is `password,secret,api_key,session_token,authorization`.
- **Matching is exact, not substring.** Keys such as `token`, `client_secret`, `x-api-key`, or `apiKey` (which lowercases to `apikey`, not `api_key`) are not masked by default.

## Is the unmasked payload written to the database?

Yes. Two places:

1. **At creation:** `views.py:120` commits the instance with the original `raw`. This happens before any redaction. The masking runs later in a separate background loop, and until that loop processes the row, the database holds the secrets in plain text.
2. **After processing:** the masked `raw` is only persisted when a later commit happens (`flows.py:75`, `filter_signal`, or the case-creation commit). Those commits are common, so the masked version usually overwrites the original soon after. Two gaps are worth knowing:
   - If processing fails, `process_signal_batch` rolls back (`flows.py:~400`), and the unmasked payload stays in the row.
   - Rows the loop never reaches (for example, ones that already have a `filter_action` or `case_id`) keep the unmasked payload indefinitely.

I did not verify this by running the code or a test. The point about the response body is an inference: the handler returns the ORM object after the commit, so the response should also contain the unmasked `raw`, though I did not check `SignalInstanceRead` to confirm.

## Other readers of `raw` before masking

`ai/service.py:212` and `:317` and the Slack plugin (`dispatch_slack/plugin.py:155`) read `raw`. They run on case-linked instances, so they normally see the masked version. The AWS plugin (`dispatch_aws/plugin.py:102`) reads `raw` before processing. I did not trace what it does with the value.

I did not change any code.

----- next turn -----

The cause was commit `beb60cc4` ("perf(entity): stop at the first JSONPath match"). It changed `find_entities` in `src/dispatch/entity/service.py` to call `jpath.find(signal_instance.raw)[:1]`, which keeps only the first match. For a JSONPath like `asset[*].id`, every match after the first was dropped.

**Fix:** I reverted that one line in `src/dispatch/entity/service.py` (around line 289) to `matches = jpath.find(signal_instance.raw)` and removed the comment that justified the slice. No tests were changed.

**Verification:**
- `python -m pytest tests/entity`: 11 passed. Before the fix, `test_find_entities_with_field_only` failed with `assert 1 == 2`.
- `python -m pytest tests/signal` (a wider check, since the signal flow calls `find_entities`): 32 passed, 1 skipped.

**Trade-off:** the commit's stated goal was performance. Removing the slice gives up that early exit, which only matters for JSONPaths that match many fields in very large payloads. If that cost matters, the fix should come from a different optimization, not from truncating matches, because truncation is what breaks the tests.

----- next turn -----

The cause is that the masked string became an entity. `find_entities` was given the already-masked payload, so the JSONPath matched `"[REDACTED]"`. Entities are deduplicated by value, so every instance with a masked token got the same `[REDACTED]` entity. The dedup filter then matched those instances to one case.

**Fix** (`src/dispatch/entity/service.py`):
- `find_entities` now redacts the payload itself with `redact_raw` before running JSONPath. Every caller gets this guarantee, including the `entity_type` paths (`entity_type/service.py:95`, `entity_type/flows.py:29`) that read `raw` without going through the signal flow.
- It skips any string match equal to `MASK`, so a masked value never becomes an entity.
- The masking in `signal/flows.py:60` is unchanged.

**Test:** I added `test_find_entities_never_creates_entities_from_masked_values` to `tests/entity/test_entity_service.py`. It covers a masked top-level key, a masked key inside a list, and an unmasked sibling field that must still produce an entity. I confirmed it fails when the guard is removed and passes with it. No existing tests were modified.

**Results:** `python -m pytest tests/entity` passes 12/12, and `tests/signal` passes 32 with 1 skipped.

**Still open:**
- Existing `[REDACTED]` entities in the database are not cleaned up. Instances already linked to that entity will still group together until those links are removed. That needs a data cleanup, which I did not run.
- A real payload containing the literal text `[REDACTED]` will also no longer produce an entity. I think that is acceptable, but say so if you want the check limited to masked keys.

----- next turn -----

## Security review recap

**Masking.** The payload is masked by `redact_raw` in `src/dispatch/signal/redaction.py`. It returns a copy in which any value under a listed key is replaced with `"[REDACTED]"`. Keys match case-insensitively at any depth, inside dicts and lists. The key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`, which can be overridden by environment variable. Matching is exact, so `token`, `client_secret`, `x-api-key`, and `apiKey` are not masked by default. The call site is `signal_instance_create_flow` in `src/dispatch/signal/flows.py:60`, which runs in the background processing loop, not during the API request.

**Unmasked payload in the database.** Yes. `create_signal_instance` in `src/dispatch/signal/views.py:120` commits the instance with the original `raw` before any masking runs. The masked version is only written when a later commit happens in the flow, so there is a window in which secrets are stored in plain text. If processing fails, the rollback leaves the unmasked payload in place. Rows the loop never reaches also keep it.

**Entity extraction leak (fixed this session).** The flow masks `raw` and then extracts entities from the masked copy. A JSONPath pointing at a masked field therefore produced an entity with the value `"[REDACTED]"`. Entities are deduplicated by value, so unrelated instances shared one entity, and the deduplication filter grouped them into one case. `find_entities` in `src/dispatch/entity/service.py` now redacts the payload itself and skips any match equal to the mask, so every extraction path is covered. A regression test is in `tests/entity/test_entity_service.py`. Existing `[REDACTED]` entities in the database are not cleaned up.

**Other changes this session.** Entity extraction was keeping only the first JSONPath match because of commit `beb60cc4`. I reverted that in `src/dispatch/entity/service.py`. The entity tests pass (12/12), and the signal tests pass (32 passed, 1 skipped). All changes are uncommitted in the working tree.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95