## Trace: `POST /api/v1/{organization}/signals/instances`

Nothing was changed. This is from reading the code; I did not run the app or the tests.

### Path

1. **Route** — `src/dispatch/signal/views.py:70-129` (`create_signal_instance`). It resolves the project, then the signal definition by `externalId` or `variant`, falling back to the default. It calls `signal_service.create_instance(...)` and then `db_session.commit()` at line 120. Nothing in the POST handler masks anything.

2. **Persist raw** — `src/dispatch/signal/service.py:650-722` (`create_instance`). It copies `raw` into a `SignalInstance` as `json.loads(json.dumps(raw))`, which only normalizes JSON. The value is not masked here.

3. **Async processing** — the POST returns and the row sits with `filter_action IS NULL` and `case_id IS NULL`. A worker loop in `src/dispatch/cli.py:~960-1010` (`process_signals`) and `src/dispatch/signal/flows.py:385-468` (`process_signal_batch`, `process_organization_signals`) picks those rows up and calls `signal_instance_create_flow`.

4. **Masking** — `src/dispatch/signal/flows.py:46-60`, `signal_instance_create_flow`. The first thing it does is:
   ```python
   signal_instance.raw = redact_raw(signal_instance.raw)  # flows.py:60
   ```
   The comment says it happens "before entities are extracted from the payload", so entity extraction sees masked data.

5. **Entities and filtering** — entity extraction runs at `flows.py:63-80` and commits if there are entity types. Then `signal_service.filter_signal` (`service.py:866-896`) runs snooze and then dedup (`filter_dedup`, `service.py:789`), and commits at line 896. If `filter_action` is set, the flow returns and no case is created. Otherwise it continues to the canary check, the `create_case` check, and then case creation (`flows.py` ~140 onward, not traced in detail).

### The masking function

- **Function:** `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` in `src/dispatch/signal/redaction.py:10-17`, with a recursive helper `_redact` (lines 20-27).
- **Behavior:** returns a copy. Any dict key whose lowercased name is in the set is replaced with `"[REDACTED]"`. The walk goes through nested dicts and lists. Non-container values are not inspected.
- **Default keys:** `config.py:98-102` reads `SIGNAL_REDACTED_RAW_FIELDS` with the default `password,secret,api_key,session_token,authorization`. The default is applied at import time, so changing the env var requires a restart.

### Is the unmasked payload written to the database?

**Yes, in two ways.**

- **Before masking, at the POST.** `views.py:120` commits the `raw` column (`models.py:239`, JSONB) exactly as the caller sent it. Any sensitive values in the request are stored unmasked from this point until the worker runs.
- **Overwrite after masking.** When the worker runs `redact_raw` and then commits (in `filter_signal`, or in the entity step), the `raw` column is overwritten with the masked copy. The original is not kept anywhere else in this code path. So the final state is masked, but the unmasked value persists for the whole queue delay.

Two related points:

- **Failure leaves it unmasked.** `process_signal_batch` and `process_organization_signals` roll back on exception. If the flow raises before its first commit, the row keeps the unmasked `raw` and is retried, because `filter_action` is still NULL. It can stay unmasked indefinitely.
- **The POST response echoes the raw payload.** `SignalInstanceRead` extends `SignalInstanceBase`, which has `raw: dict[str, Any]` (`models.py:394`). The response is built after the commit and before the worker runs, so it contains the unmasked payload.

### Other observations

- **Matching is exact on key name only.** A key like `Authorization` matches because of the lowercasing, but `x-api-key`, `auth_token`, `apiKey`, or a secret in a string value does not match. Keys are compared as `str(key).lower()` against the set, so `apiKey` is not the same as `api_key`.
- **No test covers `redact_raw`.** A grep over `tests/` finds no reference to it. The flow tests in `tests/signal/test_signal_flow.py` call `signal_instance_create_flow`, so they run the masking code, but nothing asserts on the masked output.
- I did not trace case creation after the filter step, or whether any other read path (the GET endpoints, logs, or the `consume_signals` producer in `cli.py`) exposes the raw payload.

----- next turn -----

The regression came from commit `beb60cc4` ("perf(entity): stop at the first JSONPath match"). I reverted it, and `tests/entity` now passes (11 passed). Nothing else changed.

**The cause:** the commit changed `find_entities` in `src/dispatch/entity/service.py` so each JSONPath keeps only its first match:

```python
matches = jpath.find(signal_instance.raw)[:1]
```

A JSONPath such as `asset[*].id` can match several fields, and every match should become an entity. The `[:1]` dropped all but the first.

**The fix:** I removed the slice and its comment, restoring the original line:

```python
matches = jpath.find(signal_instance.raw)
```

**Verification:**
- Before the fix, `tests/entity` failed in `test_find_entities_with_field_only` (`assert 1 == 2`). This was the only failure.
- After the fix, `tests/entity` passes (11 passed).
- `tests/signal` also passes (32 passed, 1 skipped), since the signal flow depends on entity extraction.

The change is one line in `src/dispatch/entity/service.py`. The commit's stated goal was performance. If you still want to avoid walking every match, the faster approach needs a different design, because the entity test requires every match to be kept.

----- next turn -----

The analysts' report is caused by the entity extraction code, not the masking. A masked token became an entity with the shared value `[REDACTED]`, and the dedup filter then grouped unrelated instances. I fixed it in `find_entities`, and the entity and signal suites pass.

**Why it happened:** I found two ways a masked value could become an entity. Both came from `find_entities` extracting from the raw payload:

1. **Processed instances:** `signal_instance_create_flow` masks `raw` at `flows.py:60`, then extracts entities from it. The token's JSONPath matches the string `"[REDACTED]"`, which became an entity value. Every such instance got the same entity, so the dedup filter grouped them.
2. **Entity type creation:** `entity_type/service.py` re-extracts entities from stored payloads without masking them. Instances not yet processed still hold the real token, so it was stored as an entity value.

**The fix** (`src/dispatch/entity/service.py`):
- `find_entities` now redacts the payload with `redact_raw` before matching. Every caller gets this, so the second path is covered.
- Matches whose value equals `MASK` are skipped.
- The masking in `flows.py` is unchanged.

**The test:** I added `test_find_entities_never_extracts_masked_values` to `tests/entity/test_entity_service.py`. It covers an unprocessed payload with a real token and a processed payload containing `[REDACTED]`, and expects no entities in either case. It fails against the committed `service.py` and passes with the fix.

**Results:** `tests/entity` passes (12 passed). `tests/signal` passes (32 passed, 1 skipped).

**Trade-off:** The skip is by value, so a payload that literally contains the text `[REDACTED]` will no longer produce an entity. I think that is acceptable, but say so if you want the skip to key on the redacted field name instead.

----- next turn -----

## Security review recap

**Redaction (signal instances).** The POST handler (`src/dispatch/signal/views.py:70-129`) creates the instance and commits its `raw` payload without masking. Masking happens later, in the worker, in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`). It replaces the value of any matching key with `[REDACTED]`, at any depth. Matching is case-insensitive on the key name only, so `x-api-key` or a secret inside a string value is not caught.

**Unmasked payload in the database.** Yes. The POST commit at `views.py:120` stores the raw payload before the worker runs. Once the worker masks and commits, the column holds the masked copy and the original is not kept. If the worker fails before its first commit, the unmasked payload stays in place and the row is retried.

**Entity extraction and masked values.** Two paths extracted entities from the raw payload:
- Processed instances: the masked `[REDACTED]` value became an entity. Every such instance got the same entity, so the dedup filter grouped unrelated instances.
- Entity type creation (`entity_type/service.py`): it extracted from stored payloads that could still be unmasked, so a real token could become an entity value.

**Fixes in the working tree (not committed):**
- `src/dispatch/entity/service.py`: `find_entities` now redacts the payload before matching and skips any match equal to `MASK`. Masking in `flows.py` is unchanged.
- `tests/entity/test_entity_service.py`: added `test_find_entities_never_extracts_masked_values`. It fails on the committed code and passes with the fix.
- Earlier, I reverted the first-match truncation in the same file, so the entity suite now passes.

**Test status:** `tests/entity` passes (12 passed) and `tests/signal` passes (32 passed, 1 skipped).

**Gaps and trade-offs:**
- No test covers `redact_raw` itself.
- The skip is by value, so a payload that literally contains `[REDACTED]` no longer produces an entity.
- Redaction matches key names exactly, so keys like `apiKey` or `auth_token` are not masked by default.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95