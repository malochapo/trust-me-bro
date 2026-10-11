**Short answer:** Masking happens in the background processing loop, not in the POST handler. Default masked keys are `password`, `secret`, `api_key`, `session_token`, `authorization`. Yes, the unmasked payload is written to the database, and the POST handler commits it before any masking runs. I only read the code; nothing was run or changed.

## Request path

1. **Route:** `create_signal_instance` at `src/dispatch/signal/views.py:70-129`, rate-limited to 1000/minute.
   - It resolves the project, then the signal definition by `externalId`/`variant` from `raw`, falling back to the default (`views.py:82-112`).
   - It calls `signal_service.create_instance` (`src/dispatch/signal/service.py:650`). That builds a `SignalInstance` with `raw` as a JSON round-trip copy of the input. Nothing is masked here.
   - `views.py:120` runs `db_session.commit()`. **The unmasked `raw` is persisted at this point.**
   - The response is returned right away. Processing is not done inline, and `BackgroundTasks` is injected but never used.

2. **Async processing:** `main_processing_loop` (`src/dispatch/signal/flows.py`, near line 449) runs every 60 seconds per organization. It calls `get_unprocessed_signal_instance_ids` (`service.py:900`), which selects rows with `filter_action IS NULL` and `case_id IS NULL`, up to 500 at a time. Each batch goes through `process_signal_batch` into `signal_instance_create_flow` (`flows.py:46`).

3. **Masking:** `flows.py:59-60`
   ```python
   # mask sensitive values before entities are extracted from the payload
   signal_instance.raw = redact_raw(signal_instance.raw)
   ```
   - The function is `redact_raw` in `src/dispatch/signal/redaction.py:10`, with the recursive helper `_redact` at line 20.
   - It matches **dict keys only**, case-insensitively, at any depth, including inside lists. Matching values are replaced with `"[REDACTED]"`. String values are not scanned.
   - Matching is exact after lowercasing, so `apiKey`, `api-key`, `x-api-key`, `token`, and `client_secret` are **not** masked unless added to the list.

4. **Default keys:** `src/dispatch/config.py:98-102`, `SIGNAL_REDACTED_RAW_FIELDS`, default `"password,secret,api_key,session_token,authorization"`. It is overridable via the environment variable of the same name.

5. **After masking:**
   - Entity extraction runs on the redacted `raw` (`flows.py:63-75`), and the session commits at `flows.py:75` if there are entity types.
   - `signal_service.filter_signal` (`service.py:866`) runs snooze and dedup, and commits at `service.py:896`.
   - If filtered, the flow returns at `flows.py:100`. If `canary` or `create_case` is false, it returns at `flows.py:103-107`.
   - Otherwise it goes on to case creation (`case_flows.case_new_create_flow`, around `flows.py:200`).

## Is the unmasked payload written to the DB?

**Yes, in three ways:**

- **Commit at the POST:** `views.py:120` persists the raw payload unmasked.
- **Overwrite is not guaranteed:** the masked version replaces it only when a later commit runs (`flows.py:75` or `service.py:896`). SQLAlchemy tracks the reassignment, so the next commit writes it.
- **Failure leaves it unmasked:** if the flow raises before a commit, `process_signal_batch` rolls back (`flows.py`, the `except` in `process_signal_batch`). The redaction is discarded. The instance still has no `filter_action` and no `case_id`, so it is retried every loop indefinitely with the unmasked payload in the row.

Beyond that, I have not verified the following:
- **Dead-tuple and backup retention:** Postgres row updates leave old row versions in dead tuples, WAL, and backups until they are cleaned up. This is an inference about Postgres behavior, not something I checked here.
- **The POST response:** the handler returns the instance after the unmasked commit, so the caller may get the raw payload echoed back. This depends on whether `SignalInstanceRead` includes `raw`, which I did not check.
- **Read endpoint:** `GET /instances` returns whatever is stored, so it shows unmasked data until processing has run.

## Other findings

- **No test coverage for redaction:** a grep of `tests/` finds no references to `redact`.
- **Likely crash on the `signal` path:** when the request body includes `signal`, the lookup block at `views.py:86-95` is skipped, so `signal_definition` is never assigned. Line 97 (`if not signal_definition:`) then raises `UnboundLocalError`, which surfaces as a 500. I read this from the code and did not run it.

----- next turn -----

The entity tests pass now: 11 of 11, up from 10 of 11. Only `src/dispatch/entity/service.py` changed. I did not commit.

**Cause:** commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") changed `find_entities` in `src/dispatch/entity/service.py` (around line 289) from `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. Every JSONPath entity type therefore produced at most one entity per signal. That is the regression you saw.

**Fix:** I reverted that line to `matches = jpath.find(signal_instance.raw)` and removed the comment the commit added. The commit also gave no performance benefit, because `jpath.find` still computes every match before the slice applies.

**Verification:**
- Before the fix, `python -m pytest tests/entity` gave 1 failed and 10 passed. The failure was `test_find_entities_with_field_only`, which asserted 2 entities and got 1.
- After the fix, the same command gives 11 passed.
- I did not touch any tests.

I did not run the wider test suite beyond `tests/entity`.

----- next turn -----

Masked values can no longer become entities. The fix is in `find_entities`, and I added a regression test.

**Why the cases got grouped:** the signal's entity type matches the session token by JSONPath. The normal flow masks the payload before extraction (`signal/flows.py:60`), so the match is `"[REDACTED]"`. That string became the entity value, and the dedup filter groups instances that share an entity value. Every token-bearing instance therefore got the same entity and landed in one case.

The same gap exists on other paths. The entity-type backfill (`entity_type/service.py:95`) calls `find_entities` directly on the stored `raw`. For instances whose flow has not run yet, that `raw` is still unmasked, so the backfill extracted the real token.

**Fix (`src/dispatch/entity/service.py`):**
- `find_entities` now searches `redact_raw(signal_instance.raw)` instead of the raw payload. This covers every caller, including the backfill.
- Matches whose value equals `MASK` are skipped, as a second guard.
- The masking itself in `redaction.py` and the flow is unchanged.

**Test (`tests/entity/test_entity_service.py`):** `test_find_entities_never_returns_masked_values` uses an unmasked payload with a `session_token` and a `user.name`. It asserts that only `"alice"` comes back and the mask never appears. I added it without changing existing tests.

**Verification:** `tests/entity` passes (12 of 12), and `tests/signal` plus `tests/entity_type` pass (38 passed, 1 skipped). The new test fails against HEAD, but that check also removed the earlier `[:1]` revert, so it does not isolate this fix. I did not commit.

**Noticed, not fixed:**
- `recalculate_entity_flow` in `entity_type/flows.py:26` assigns `entity_types = ....append(entity_type)`, which sets `entity_types` to `None`. It then never extracts entities.
- The `UnboundLocalError` at `signal/views.py:97` from my earlier trace is still there. It happens when the request body includes `signal`.

----- next turn -----

The security review recap is below. The five result lines are at the end, in a code block so the format stays exact.

**Request path and masking**
- `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `src/dispatch/signal/views.py:70-129`. It creates the instance and commits it at `views.py:120`, before any masking happens.
- Masking runs later, in the background processing loop. `signal_instance_create_flow` in `src/dispatch/signal/flows.py:59-60` calls `redact_raw`, which is defined in `src/dispatch/signal/redaction.py`.
- It masks dict keys only, matched case-insensitively at any depth, with values replaced by `"[REDACTED]"`. It does not scan string values, and it does not match variants such as `apiKey` or `x-api-key`.
- The default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98-102`, and can be overridden by the environment variable of the same name.
- The unmasked payload is written to the database at the POST commit. The masked version overwrites it only when a later flow commit runs. If the flow fails, the redaction is rolled back and the unmasked payload stays in the row while the instance is retried.

**Extraction and the grouping bug**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath match in `find_entities`. That reduced every JSONPath entity type to one entity per signal. I reverted it. `tests/entity` now passes.
- Masked values became entities because `find_entities` ran on the masked payload in the normal flow, so the entity was `"[REDACTED]"`. The backfill in `entity_type/service.py:95` ran on the unmasked stored payload. Dedup groups by entity value, so unrelated token instances collapsed into one case.
- I fixed this in `find_entities`: it now searches a redacted copy of the payload and skips any match equal to the mask. Test `test_find_entities_never_returns_masked_values` was added. The masking in `redaction.py` and the flow is unchanged.

**Open items, not fixed**
- `signal/views.py:97` raises `UnboundLocalError` (a 500) when the request body includes `signal`, because `signal_definition` is never assigned on that path. I found this by reading the code and did not run it.
- `recalculate_entity_flow` in `entity_type/flows.py:26` assigns `entity_types` to the result of `.append(...)`, which is `None`, so it never extracts entities.

**Other notes**
- Changes are uncommitted: `src/dispatch/entity/service.py` and `tests/entity/test_entity_service.py`.
- `tests/signal` and `tests/entity_type` pass (38 passed, 1 skipped), along with `tests/entity` (12 of 12).

```
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95
```