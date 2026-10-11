## Short answer

- **Where masking happens:** `redact_raw` in `src/dispatch/signal/redaction.py:10`, called from `signal_instance_create_flow` in `src/dispatch/signal/flows.py:60`. The POST handler does not mask anything.
- **Default keys:** `password`, `secret`, `api_key`, `session_token`, `authorization` (`src/dispatch/config.py:98-101`, overridable via `SIGNAL_REDACTED_RAW_FIELDS`).
- **Is the unmasked payload written to the database?** Yes. The POST handler stores the raw payload unmasked and commits it before masking runs. The redacted version only overwrites it in a later commit, which happens during background processing.

## The path

1. **`POST /api/v1/{organization}/signals/instances`**, `src/dispatch/signal/views.py:70`. It resolves the project and the signal definition, then calls `signal_service.create_instance` and `db_session.commit()` (`views.py:117-120`). It returns the instance. It does not call the flow.

2. **`create_instance`**, `src/dispatch/signal/service.py:650`. It builds the `SignalInstance` with `raw=json.loads(json.dumps(...))`, a copy of the input with no masking (around `service.py:680`). The row is committed in step 1 with the raw payload in full.

3. **Background processing.** `main_processing_loop` (`flows.py:441`) runs `process_organization_signals` (`flows.py:406`) every `LOOP_DELAY` (60s). It selects instances with `filter_action IS NULL` and `case_id IS NULL` (`service.py:900`, up to 500 per pass). Those are sent to `process_signal_batch` (`flows.py:385`), which calls `signal_instance_create_flow` and commits after each instance.

4. **`signal_instance_create_flow`**, `flows.py:46`:
   - `flows.py:60`: `signal_instance.raw = redact_raw(signal_instance.raw)`. This is in memory only.
   - `flows.py:63-75`: entity extraction runs on the redacted payload. If any entity types apply, the session commits (`flows.py:75`), which persists the redacted `raw`.
   - `flows.py:~80`: `filter_signal` (`service.py:866`) runs snooze and dedup. It sets `filter_action` and commits (`service.py:~897`). If the signal is filtered, the flow returns here.
   - Otherwise, canary and `create_case` checks follow. Case creation is at `flows.py:~170-191` and commits at `flows.py:191`. The case title and description come from the signal definition, not the raw payload.

## The redaction function

`_redact` (`redaction.py:20`) walks dicts and lists recursively, at any depth.

- Keys are matched after `str(key).lower()` against the lowercased field names.
- Matching is exact after lowercasing. `apiKey`, `api-key`, and `x-api-key` do **not** match `api_key`. I checked the `apiKey` case directly.
- Only dict keys are checked. String values are not scanned, so a token in a free-text field, such as `"Authorization: Bearer ..."` inside a message, is not masked.
- Tuples and sets are not traversed.
- `token`, `key`, and `cookie` are not in the defaults.

## Caveats

- **Unmasked window.** From the POST commit until the first processing commit (up to about 60s plus batch time), the unmasked payload is in the `signal_instance.raw` JSONB column. It is also readable through `GET /instances` (`views.py:65`) to anyone with access. Nothing overwrites it on the POST path.
- **Rollback path.** If the flow raises before its first commit, `process_signal_batch` rolls back (`flows.py:~400`). The redaction is discarded, the row keeps the unmasked payload, and the instance is retried on the next pass because its `filter_action` and `case_id` are still null.
- **No tests.** A grep for `redact` under `tests/` found nothing, and there are no test references to `SIGNAL_REDACTED_RAW_FIELDS`. The masking behaviour is unverified by the suite.
- **Other ingestion paths.** `signal/flows.py:231-262` (`create_signal_instance`) and the CLI at `cli.py:1004` also create instances. I did not verify whether they go through the same redaction step.

I did not change any code.

----- next turn -----

The change responsible is commit `beb60cc4` ("perf(entity): stop at the first JSONPath match"). It added `[:1]` to the JSONPath match list in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`), so only the first match became an entity. I reverted that line. The diff is a single restored line:

```python
matches = jpath.find(signal_instance.raw)
```

**Verification**
- `python -m pytest tests/entity -q`: before the fix, 1 failed and 10 passed (`test_find_entities_with_field_only`, `assert 1 == 2`). After the fix, 11 passed.
- `python -m pytest tests/signal -q`: 32 passed, 1 skipped. I ran this because signal processing also calls `find_entities`.

No tests were changed.

**Choice I made:** I reverted the line rather than keeping the performance change and handling multi-match differently. The commit's rationale ("a JSONPath names one field") is wrong for wildcard paths like `asset[*].id`, which the existing test expects to return both values. If the perf goal still matters, the cost of `find` on large payloads would need a separate change, which I did not attempt.

----- next turn -----

The root cause is that masking replaces the value with the string `"[REDACTED]"`, and entity extraction treats that string as a normal value. Every instance of that signal gets the same `"[REDACTED]"` entity, and the dedup filter groups instances that share an entity, so unrelated tokens collapse into one case.

**Why it happened**
- `signal_instance_create_flow` masks `raw` before extraction (`flows.py:60`). That is correct, but the masked value is still a string, and `_find_entities_by_jsonpath_expression` accepted any string.
- The entity type's JSONPath points at `session_token`, so the masked field produced the `"[REDACTED]"` entity. `get_by_value_or_create` reuses one row for that value.
- Dedup (`filter_dedup`, `service.py`) joins on shared entity IDs, so all of those instances matched.
- Two other callers re-extract from the stored `raw`, which can still be unmasked for instances that were never processed: `entity_type/service.py:95` and `entity_type/flows.py:29`. Masking only in the signal flow would not cover them.

**The fix** (`src/dispatch/entity/service.py`)
- `find_entities` now searches `redact_raw(signal_instance.raw)` instead of the raw payload, so every caller sees masked data.
- It skips any match whose value equals `MASK`.
- Masking is unchanged: `redact_raw` and the call in `flows.py` are untouched.

**Test** (`tests/entity/test_entity_service.py`, new `test_find_entities_skips_masked_values`)
- It sets an unmasked `session_token` on the fixture and checks that a `session_token` entity type produces no entities and that `"[REDACTED]"` is never a value.
- It also checks that an unmasked field, `asset[0].id`, still produces its entity.
- With the mask check removed, the new test fails. With the fix in place, it passes.

**Results**
- `python -m pytest tests/entity tests/signal -q`: 44 passed, 1 skipped.
- I did not run the full suite.

**Choices to review**
- The skip compares by value, so a payload field whose literal text is `"[REDACTED]"` is also skipped. I judged that acceptable; a precise alternative would track which paths were masked.
- The fix is uncommitted and sits alongside the revert from the previous task in the same working tree.
- I reproduced the mechanism in the test and by reading the code. I did not reproduce it against a live database with a real GitHub payload.

----- next turn -----

## Security review recap

**Where masking happens.** The raw payload is masked in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`), which calls `redact_raw` in `src/dispatch/signal/redaction.py`. The POST handler (`src/dispatch/signal/views.py`) does not mask anything. Masking runs in the background processing loop, after the request has returned.

**Default keys.** `password`, `secret`, `api_key`, `session_token`, `authorization` (`src/dispatch/config.py:98`, overridable with `SIGNAL_REDACTED_RAW_FIELDS`). Matching is case-insensitive on dict keys only, at any depth. Values are not scanned, so `apiKey` and `api-key` do not match `api_key`.

**Unmasked data in the database.** Yes. `create_instance` stores the raw payload as received, and the POST commits it before masking runs. The masked version overwrites it only in a later commit during processing. If processing fails before its first commit, the rollback discards the masking and the row keeps the unmasked payload. Until processing runs, `GET /instances` also returns it.

**Extraction bug.** Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]`, so only the first match became an entity. I reverted that line in `src/dispatch/entity/service.py`. `tests/entity` went from 1 failing to 11 passing.

**Grouping bug.** Masking replaces the value with the string `"[REDACTED]"`, and extraction treated that string as a normal value. Every instance then shared one `"[REDACTED]"` entity, and dedup grouped them. `find_entities` now searches the redacted payload and skips any match equal to `MASK`. Masking itself is unchanged. I added `test_find_entities_skips_masked_values`, which fails without the check and passes with it. `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**Open items**
- The fixes are uncommitted in the working tree. The grouping fix and the extraction revert both touch `src/dispatch/entity/service.py`.
- The skip compares by value, so a literal `"[REDACTED]"` in a payload is also skipped.
- The full test suite was not run.
- Unmasked payloads still sit in the database until processing runs. Moving masking into the POST path would close that window, but I have not changed it.

```
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95
```