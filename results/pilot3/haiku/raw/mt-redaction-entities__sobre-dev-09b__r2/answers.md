The raw payload is stored unmasked. Masking happens later, in a background worker, and the API response also returns the unmasked payload. I made no code changes.

**Request path**

1. **Route:** `create_signal_instance` in `src/dispatch/signal/views.py:70-120`, mounted at `POST /api/v1/{organization}/signals/instances`.
2. **Service:** the view calls `signal_service.create_instance` (`src/dispatch/signal/service.py:650`). It copies `raw` into the `SignalInstance` model (`raw=json.loads(json.dumps(...))` at line 680 and again at 737) and calls `db_session.add`. No masking happens here.
3. **Commit:** the view calls `db_session.commit()` (`views.py:~118`) right after `create_instance`. **The unmasked payload is durably written at this point.**
4. **Response:** the view returns the ORM object as `SignalInstanceRead`, which inherits `raw` from `SignalInstanceBase` (`signal/models.py:394`). The unmasked payload is therefore returned to the caller. I inferred this from the class hierarchy and did not run it.
5. **Processing:** the API does not call the flow inline. A background loop in `process_signals` (`src/dispatch/cli.py:938`, around line 1004) picks up up to 500 rows with `filter_action IS NULL` and `case_id IS NULL`. It calls `signal_flows.signal_instance_create_flow` (`src/dispatch/signal/flows.py:46`), either directly or through `process_signal_batch` (`flows.py:385`).

**Where masking happens**

- **Function:** `redact_raw` in `src/dispatch/signal/redaction.py`. It is called at `src/dispatch/signal/flows.py:60`, as the first step of `signal_instance_create_flow`, before entity extraction. The comment there says the masking is meant to happen before entities are extracted.
- **Behaviour:** it returns a new structure. Any dict key whose lowercased name matches the set is replaced with `"[REDACTED]"`. Matching is case-insensitive and applies at any depth, including inside lists. Non-dict and non-list values pass through unchanged.
- **Default keys:** `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98-102`, configurable via the environment variable of the same name. The default is `password,secret,api_key,session_token,authorization`.
- **Matching is exact, not substring.** Keys such as `apiKey`, `x-api-key`, `access_token`, `token` or `cookie` are not masked by default.

**Is the unmasked payload written to the database?**

Yes, in two places:

- **At the API commit.** `views.py` commits the raw payload before any masking runs. Any row the worker never processes stays unmasked. That includes rows where the flow raises an exception, or where the worker is not running.
- **Afterwards, the masked value overwrites it.** The flow sets `signal_instance.raw` to the redacted copy, and later commits in the flow (the commit after entity assignment, and `filter_signal`'s commit at `service.py:896`) persist the masked value. So the unmasked value is durable only until the worker processes the row.

I found no tests for `redact_raw` (a grep of `tests/` for `redact` returned nothing).

**Filtering and case creation**

After masking, the flow extracts entities (`entity/service.py:290`, which reads `signal_instance.raw` via JSONPath), then runs `signal_service.filter_signal` (snooze, then dedup). If a filter action is set, the flow returns early and the instance is not turned into a case. Otherwise it returns early for canary signals or for signal definitions with `create_case` disabled. Otherwise it creates the case.

**Things I did not verify**

- `flows.py:253` builds a second `SignalInstanceCreate` with `raw=signal_instance_data`. I did not trace which path calls that, and whether it bypasses the API route.
- I did not check whether the `raw` JSONB column or the database has any other copies, such as logs or replication.

The practical gap is the first commit in `views.py`. Masking the payload before that commit would close it, and the response would need the same treatment.

----- next turn -----

The cause was commit `beb60cc4` ("perf(entity): stop at the first JSONPath match"). It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`, which keeps only the first match. I reverted that line to `matches = jpath.find(signal_instance.raw)` and removed the comment that came with it.

**Verification**
- Before the fix, `tests/entity` failed with `test_find_entities_with_field_only`: `assert 1 == 2`. The test expects two matches to become two entities.
- After the fix, `python -m pytest tests/entity` gives 11 passed.
- `python -m pytest tests/signal` gives 32 passed, 1 skipped. The skip was already there, and I didn't check why.

**Why the revert and not a different optimisation**
The commit message said "perf", but the slice saves nothing. `jpath.find` returns a full list eagerly, so the work is already done before the slice. If you want a real speed-up, it would need a different approach, such as a lazy iterator, and that's a separate change.

I didn't modify any tests. The only change is in `src/dispatch/entity/service.py`, and `git status` shows that file alone.

----- next turn -----

Masked values can no longer become entities. The regression test fails without the fix and passes with it.

**Why the instances grouped**

In the normal flow, `signal_instance_create_flow` masks `raw` (`flows.py:60`), then calls `find_entities`. The signal's JSONPath for the session token therefore matched the string `"[REDACTED]"`, and that string became the entity value. Every instance got the same entity, and the deduplication filter on that entity type put them in one case. I inferred this from the code; I did not reproduce the full case-grouping end to end.

**Fix** (`src/dispatch/entity/service.py`)

- `find_entities` now searches a redacted copy of the payload, `redact_raw(signal_instance.raw)`, so the search can't see the original secret even if the stored row is still unmasked.
- Any match whose value is `MASK` is skipped.
- I kept the masking in `redaction.py` and the call in `flows.py` unchanged.

This guard covers every caller of `find_entities`, which matters because two other paths extract entities from stored payloads. `entity_type/service.py:95` re-runs extraction over a case's instances when an entity type is created, and those rows may not have been processed yet. Before this change, that path could create entities from the original secret.

One side effect: a payload value that is literally `"[REDACTED]"` is also skipped. That's indistinguishable from a masked value, so I accepted it.

**Test** (`tests/entity/test_entity_service.py`)

`test_find_entities_never_creates_entities_from_masked_values` covers two cases:
- A JSONPath naming a masked field produces no entities.
- A `$.*` wildcard keeps only the unmasked `"alice"`.

**Verification**

- `python -m pytest tests/entity tests/signal` gives 44 passed, 1 skipped. The skip was already there.
- With only the source fix stashed, the new test fails. With it restored, the whole entity suite passes.

**Things I noticed but did not change**

- `entity_type/flows.py:27-29` assigns the result of `signal_instance.signal.entity_types.append(entity_type)`, which returns `None`. So `recalculate_entity_flow` never extracts anything. This is pre-existing and separate from this bug.

----- next turn -----

Here's the recap. The working tree has uncommitted changes in `src/dispatch/entity/service.py` and `tests/entity/test_entity_service.py`. Nothing is committed.

**Request path and masking**
- `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `src/dispatch/signal/views.py`. It stores the payload with `signal_service.create_instance` and commits, before any masking.
- A background loop (`process_signals` in `src/dispatch/cli.py`) later runs `signal_instance_create_flow` (`src/dispatch/signal/flows.py`), which masks `raw` before entity extraction and filtering.
- Masking is `redact_raw` in `src/dispatch/signal/redaction.py`. Keys match case-insensitively at any depth. Default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`. Matching is exact, so `apiKey` or `access_token` are not masked by default.
- The unmasked payload is written to the database at the API commit, and the API response also returns it. The later masked write only happens if the worker processes the row.

**Fixes made in this session**
- **Entity extraction (`beb60cc4`)**: that commit added `[:1]` to the JSONPath matches, so only one entity was kept. I reverted the slice. `tests/entity` passes.
- **Masked values as entities**: the flow masks `raw` and then extracts entities, so a JSONPath on a masked field matched `"[REDACTED]"` and created a shared entity. Dedup then grouped unrelated instances. `find_entities` now searches a redacted copy and skips the mask value. The new test `test_find_entities_never_creates_entities_from_masked_values` fails without the fix. Masking itself is unchanged.

**Not verified or not fixed**
- I did not reproduce the full case grouping end to end. The mechanism comes from reading the code.
- `recalculate_entity_flow` in `src/dispatch/entity_type/flows.py` assigns the result of `.append(...)`, which is `None`, so it never extracts anything. This is pre-existing and I left it alone.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95