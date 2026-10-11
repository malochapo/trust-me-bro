The payload is masked in memory, but the unmasked version is written to the database at POST time and only overwritten later, by the background processor. I did not change any code.

## Request path

1. **`POST /api/v1/{organization}/signals/instances`** → `create_signal_instance` in `src/dispatch/signal/views.py:70-124`. It resolves the project, then the signal definition by `raw.externalId`/`raw.variant`, falling back to the default. It returns 404 if none exists. It calls `signal_service.create_instance` (`service.py:650`), commits, and returns the row. It does **not** run the case-creation flow. The `background_tasks` parameter is unused.
2. **Later, asynchronously**, `process_organization_signals` → `process_signal_batch` (`signal/flows.py:385-439`) calls `signal_instance_create_flow` (`flows.py:46`) on rows where `filter_action` and `case_id` are both NULL, oldest first, up to 500 per organization. A second caller is the CLI at `src/dispatch/cli.py:1004`. I did not find where `main_processing_loop` (`flows.py:441`) is started; nothing in `src/` calls it.
3. **Inside the flow:**
   - Redact `raw` (`flows.py:59-60`).
   - Find entities on the redacted payload and commit (`flows.py:62-75`).
   - Run `signal_service.filter_signal`. If it filters, return here (`flows.py:77-94`). Deduplicated instances update their conversation message if one exists.
   - Canary instances and signals with `create_case=False` return without a case.
   - Otherwise create a case (`flows.py:~160-190`), link it, then run `case_flows.case_new_create_flow`, engagement, and workflows.

## Masking

- **Function:** `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` in `src/dispatch/signal/redaction.py:10`, with the recursive helper `_redact` below it. It returns a copy and replaces the value of any matching key with `"[REDACTED]"`.
- **Matching:** case-insensitive exact key match, at any depth inside dicts and lists. Substrings do not match, so `x-api-key` and `apiKey` are not masked. Only keys are checked; secret-looking string values under other keys are left alone.
- **Default keys:** `password,secret,api_key,session_token,authorization`, from `src/dispatch/config.py:98-102`. Override with the `SIGNAL_REDACTED_RAW_FIELDS` env var. Those are the defaults; no other keys are masked.
- **Only call site:** `flows.py:60`. Nothing in the POST handler or the service masks.

## Is the unmasked payload written to the database?

**Yes.** Two points in the path persist it:

1. **At POST time.** `service.create_instance` sets `raw=json.loads(json.dumps(raw))` (`service.py:680`), which is a plain copy with no redaction. The view commits it (`views.py:118-119`). The `signal_instance.raw` JSONB column holds the full secret values from the request until the background processor runs. That window is at least one loop cycle (`LOOP_DELAY` is 60 s) plus any queueing.
2. **The response.** The handler returns the in-memory row, and `SignalInstanceRead` includes `raw` (`signal/models.py:389-410`). Because the flow has not run yet, the caller gets the unmasked payload back.

After processing, the flow overwrites `raw` with the masked copy and commits it. That fixes the stored value going forward, but it does not remove the earlier unmasked version from the database's history, WAL, or backups. If the flow raises, `process_signal_batch` rolls back, so the row stays unmasked and is retried.

Instances filtered out, canary instances, and `create_case=False` instances are masked in the stored row, since they all return after redaction.

## Gaps

- No test references `redact` (`grep` found none in `tests/`). The flow tests in `tests/signal/test_signal_flow.py` do not assert masking.
- I did not read `filter_signal` or `case_flows.case_new_create_flow` internals, so I have not checked whether they log or copy `raw`.
- I did not find where `main_processing_loop` is started, so the actual processing cadence in production is unconfirmed.

----- next turn -----

The regression came from commit `beb60cc4` ("perf(entity): stop at the first JSONPath match"). I reverted its one-line change, and `tests/entity` now passes (11/11).

**The cause:** the commit changed `src/dispatch/entity/service.py:289` from `matches = jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. That slice keeps only the first match, so a JSONPath like `asset[*].id` produced one entity instead of one per match. The commit also didn't speed anything up, because `jpath.find` has already computed every match before the slice.

**The fix:** I restored the original line, which is the only change in the working tree (`git status` shows only `src/dispatch/entity/service.py` modified). I did not touch any tests.

**Verification:**
- `python -m pytest tests/entity -q`: 11 passed. Before the fix, `test_find_entities_with_field_only` failed with `assert 1 == 2`.
- `python -m pytest tests/signal -q`: 32 passed, 1 skipped. I ran this because the signal flow depends on entity extraction.

I have not committed anything.

----- next turn -----

Fixed. Entity extraction was turning the masked value `"[REDACTED]"` into an entity. Every instance with a masked token therefore produced the same entity value, and the deduplication filter grouped them into one case. The masking itself is unchanged.

**Root cause:** `redact_raw` replaces a secret with the string `"[REDACTED]"`. The signal flow runs redaction before entity extraction, which is correct, but `_find_entities_by_jsonpath_expression` in `src/dispatch/entity/service.py` only checked `isinstance(match.value, str)`. The sentinel is a string, so it passed, and the JSONPath on the session token produced the entity `[REDACTED]`. The deduplication filter then matched all those instances on that shared value.

**Fix:** `find_entities` now skips any match equal to `MASK` (`src/dispatch/entity/service.py:290-293`, importing `MASK` from `dispatch.signal.redaction`). I put the guard in the shared extraction function rather than the signal flow because `find_entities` also runs from `entity_type/service.py` (when an entity type is added to a case) and `entity_type/flows.py`. The guard covers every path, even if a caller forgets to redact first.

**Test:** I added `test_find_entities_skips_masked_values` to `tests/entity/test_entity_service.py`. It masks two payloads with different tokens through `redact_raw`, then checks that the token entity type yields nothing and the `user` entity type still produces its value. With the guard removed it fails with `{'[REDACTED]', 'user-of-token-one'}`. With the guard it passes. I did not change any existing tests.

**Verification:** `python -m pytest tests/entity tests/signal tests/entity_type -q` gives 50 passed, 1 skipped.

**Also noticed, not fixed:** in `src/dispatch/entity_type/flows.py`, `entity_types = signal_instance.signal.entity_types.append(entity_type)` assigns `None` (`append` returns nothing), so the `if entity_types:` block never runs. That looks like an unrelated pre-existing bug, and it's outside this change. Also, the earlier `[:1]` revert is still part of the working tree, so the diff against HEAD includes it. Nothing is committed.

----- next turn -----

Recap of the security review and the two fixes. Nothing is committed; the changes are in the working tree.

**Masking and the database.** The masking function is `redact_raw` in `src/dispatch/signal/redaction.py`. It masks values whose keys match, case-insensitively and at any depth, and replaces each with `"[REDACTED]"`. It runs once, in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`), before entity extraction and filtering. Default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98-102`. Masking is unchanged.

The unmasked payload is written to the database. `service.create_instance` stores `raw` as received, and the POST handler commits it before the background flow runs. The flow later overwrites `raw` with the masked copy, but the original stays in database history, WAL, and backups. The POST response also echoes the unmasked `raw` back to the caller.

**Entity extraction bug.** Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]`, which kept only the first JSONPath match. I reverted that line in `src/dispatch/entity/service.py`. `tests/entity` went from 1 failed to 11 passed.

**Masked values grouping cases.** `"[REDACTED]"` is a string, so the JSONPath on the session token produced it as an entity. Every instance with a masked token then shared that entity value, and the deduplication filter grouped them into one case. `find_entities` now skips any match equal to `MASK`, so the guard covers the signal flow and the `entity_type` reprocessing paths. I added `test_find_entities_skips_masked_values` to `tests/entity/test_entity_service.py`. It fails with the guard removed and passes with it. `tests/entity`, `tests/signal`, and `tests/entity_type` give 50 passed, 1 skipped.

**Not fixed:** `src/dispatch/entity_type/flows.py` assigns `signal.entity_types.append(...)`, which returns `None`, so the block that follows never runs. This is unrelated to this change, so I left it alone.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95