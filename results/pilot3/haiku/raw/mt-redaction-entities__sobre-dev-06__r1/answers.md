The raw payload is masked in `redact_raw`, but only after the unmasked payload has already been committed to the database. Masking happens in a later batch job, not in the POST request. I made no code changes.

## Path from POST to case or filter

1. **Route:** `create_signal_instance` in `src/dispatch/signal/views.py:70-101` resolves the project and signal definition (by `externalId`/`variant`, else the default). It calls `signal_service.create_instance`, then commits.
2. **Persist:** `create_instance` in `src/dispatch/signal/service.py` (around line 680) stores `raw=json.loads(json.dumps(...))`. This is the unmasked payload. The route commits it with `filter_action` and `case_id` still NULL. The POST response is `SignalInstanceRead`, which includes `raw`, so the caller also gets the unmasked payload back.
3. **Batch pickup:** nothing processes the instance inline. The continuous loop in `src/dispatch/cli.py` (around lines 935-1010) selects instances where `filter_action IS NULL AND case_id IS NULL`, up to 500 per pass, and calls `signal_instance_create_flow`. `process_organization_signals` and `process_signal_batch` in `src/dispatch/signal/flows.py:385-431` do the same thing in batches of 50.
4. **`signal_instance_create_flow`** (`src/dispatch/signal/flows.py:46`):
   - **Line 59-60:** `signal_instance.raw = redact_raw(signal_instance.raw)`. This is the masking step, and it runs before entity extraction.
   - Entity extraction, then `filter_signal` (`service.py:866`). That runs snooze, then dedup, and sets `filter_action` to `none` or a filter action. Its `db_session.commit()` at `service.py:896` is the first commit of the redacted payload.
   - **Filtered:** returns early. Dedup and snooze are the filter actions.
   - **Canary:** returns after storing the instance, with the redacted payload.
   - **`create_case` false:** returns.
   - **Otherwise:** the case is created from the case type, priority, and oncall settings. I did not trace case creation in detail.

## Masking function

- **Function:** `redact_raw` in `src/dispatch/signal/redaction.py:10-17`, with recursive helper `_redact` at lines 20-28.
- **Behavior:** it returns a copy. Keys are matched case-insensitively at any depth, through dicts and lists, and each matching value becomes `"[REDACTED]"`. It matches on key names only, not on value contents.
- **Default keys:** `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98-102`, overridable by env var. Default: `password, secret, api_key, session_token, authorization`.
- **Matching is exact after lowercasing.** `apiKey` lowercases to `apikey`, which does not match `api_key`. `client_secret`, `access_token`, `token`, and `api-key` are not masked by default either. Only the five exact key names are covered. String values containing secrets are not masked.

## Is the unmasked payload written to the database?

Yes, in two cases:

- **Between POST and processing:** the unmasked `raw` is committed by the POST route. It stays unmasked until a batch pass runs the flow. A new instance is unmasked for as long as it waits in the queue.
- **If processing keeps failing:** the redaction is in memory until `filter_signal` commits. `process_signal_batch` calls `rollback()` on error, so a failing instance stays unmasked in the database and is retried on every pass. I did not confirm the rollback in the `cli.py` loop's inner exception handler.

Once processing succeeds, the redacted payload overwrites the stored one. No separate copy of the original is kept in `signal_instance`. I did not check other tables, logs, or events for copies of the payload.

## Other observations

- `update_instance` (`service.py:~737`) writes `raw` without redaction. I did not check its callers.
- The scheduler and AWS plugin path (`flows.py:236-260`, `plugins/dispatch_aws/plugin.py:93`) creates instances without calling `redact_raw`. Those instances are still masked later by the batch loop, because the loop picks up every instance with NULL `filter_action`.

----- next turn -----

The cause was commit `beb60cc4` ("perf(entity): stop at the first JSONPath match"). It changed `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]` in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`, around line 289). That slice keeps only the first match, so a JSONPath like `asset[*].id` produced one entity instead of one per field.

I reverted that line to the original `matches = jpath.find(signal_instance.raw)` and removed the comment the commit added. The change is one line in `src/dispatch/entity/service.py`. I did not touch any tests.

Results with the local PostgreSQL:
- `python -m pytest tests/entity`: 11 passed.
- `python -m pytest tests/signal tests/entity_type`: 38 passed, 1 skipped.

The commit's stated goal was performance. Removing the slice means every JSONPath match is now evaluated and yielded. If the perf concern still matters, the fix belongs in a different place, such as capping matches per entity type, not in the first-match cutoff. I didn't investigate whether that concern is real.

----- next turn -----

The grouping came from the mask string itself. Fixed, with a regression test, and the masking code is unchanged.

**Why it happened**

1. For the signal, `signal_instance_create_flow` redacts `raw` (`src/dispatch/signal/flows.py:60`), then calls `find_entities`.
2. The entity type's JSONPath matches the `session_token` key, so the match value is the literal `"[REDACTED]"`. `find_entities` turned that into an entity.
3. Every instance of the signal got the same entity value, so the deduplication filter (which joins on entities) grouped unrelated instances.

A second path had the same exposure. `entity_type/service.py:95` runs `find_entities` over `signal_instance.raw` as stored in the database. For instances not yet processed, that raw is still unmasked, so a real token could become an entity.

**The fix** (`src/dispatch/entity/service.py`)

- `find_entities` now searches `redact_raw(signal_instance.raw)` instead of the raw payload. Every extraction path goes through this function, so every path sees masked data.
- Matches equal to `MASK` are skipped, so a masked value can't become an entity.
- `redact_raw` and the masking in the flow are untouched.

**Test** (`tests/entity/test_entity_service.py`, new test appended)

`test_find_entities_never_returns_masked_values` builds an instance with an unmasked `session_token` at the top level and inside a list. It asserts that neither JSONPath yields an entity, and that an unmasked `user` field still does. With the fix temporarily removed, the new test fails; with it restored, it passes.

**Results:** `python -m pytest tests/entity tests/signal tests/entity_type`: 50 passed, 1 skipped.

**What changes for analysts:** a JSONPath that targets a masked key no longer creates entities. A deduplication filter on that entity type will therefore no longer group instances by that token. That is the intended outcome, but the existing filter on that type will match nothing.

**Not changed, for you to decide:**
- `src/dispatch/entity_type/flows.py:29` is broken: `entity_types = ....append(entity_type)` assigns `None`, so its `if entity_types:` block never runs. It's out of scope here.
- `find_entities` never evaluates `regular_expression`; only JSONPath is used. So there is no regex-based extraction to mask.

----- next turn -----

## Security review recap

**Where masking happens:** `redact_raw` in `src/dispatch/signal/redaction.py`, called from `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`). It returns a copy in which any dict key matching a configured name (case-insensitive, at any depth, through lists) has its value replaced by `"[REDACTED]"`. The default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`. Matching is exact after lowercasing, so `apiKey`, `api-key`, `token`, and `client_secret` are not masked by default.

**Database exposure:** The POST route commits the unmasked payload before any processing. It stays unmasked until the batch job runs the flow. If processing keeps failing, the rollback leaves the row unmasked, so the exposure can persist. The POST response also returns the unmasked `raw`. Once processing succeeds, the redacted payload overwrites the stored one.

**Bugs found and fixed this session:**
- **Entity extraction, first match only:** the commit `beb60cc4` added `[:1]` to the JSONPath match list. I reverted that line, and `tests/entity` passes.
- **Masked values becoming entities:** a JSONPath that matched a masked key yielded `"[REDACTED]"` as an entity value. Every instance then shared that entity, and the dedup filter grouped them. `find_entities` now searches the redacted payload and skips the mask sentinel. This also covers `entity_type/service.py`, which read unmasked raw from the database. A regression test was added to `tests/entity/test_entity_service.py`. It fails without the fix and passes with it. `tests/entity`, `tests/signal`, and `tests/entity_type` pass together: 50 passed, 1 skipped.

**Open items I did not change:**
- `signal/service.py` `update_instance` writes `raw` without redaction. I did not check its callers.
- `entity_type/flows.py:29` assigns `None` to `entity_types`, so its extraction block never runs.
- `find_entities` never evaluates `regular_expression`, so there is no regex path to mask.
- I did not trace case creation after the create-case branch.

```
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95
```