**Short answer:** the masking happens in `redact_raw` (`src/dispatch/signal/redaction.py:10`), called from `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`). By default it masks `password`, `secret`, `api_key`, `session_token`, and `authorization`. Yes, the unmasked payload is written to the database: the POST handler commits the raw payload before any masking runs, and masking only overwrites it later, once the processing loop picks the instance up.

**Path from POST to case or filter**

1. **Route:** `POST /api/v1/{organization}/signals/instances` is `create_signal_instance` in `src/dispatch/signal/views.py:70`. It resolves the project, then finds a signal definition by `externalId`/`variant` in `raw`, falling back to the project default (lines ~70–113). It is rate-limited to 1000/minute.
2. **Persist raw, unmasked:** it calls `signal_service.create_instance` (`signal/service.py:650`), which stores `raw` as a JSON round-trip of the input (`service.py:680`). The handler then calls `db_session.commit()` (views.py ~line 115). The `background_tasks` parameter is declared but never used, and nothing in the handler calls the flow. The response also serializes `raw` before any masking.
3. **Processing happens later:** `signal_instance_create_flow` runs from the `main_processing_loop` in `signal/flows.py:441` (every 60 seconds per organization), from the `dispatch signals process` CLI command (`cli.py:938`, which queries unprocessed rows directly), and from `process_signal_batch`. It selects rows with `filter_action IS NULL` and `case_id IS NULL`. The AWS plugin path (`plugins/dispatch_aws/plugin.py:113`) calls `create_signal_instance`, which is the same storage path as the API.
4. **Masking:** `signal_instance_create_flow` sets `signal_instance.raw = redact_raw(signal_instance.raw)` (`flows.py:59–60`), before entity extraction.
5. **Entities:** `entity_service.find_entities` runs on the masked raw. JSONPath matching uses `signal_instance.raw` (`entity/service.py:290`), so entities are extracted from the masked payload.
6. **Filtering:** `signal_service.filter_signal` (`signal/service.py:866`) runs snooze, then deduplication (`filter_dedup`, line 789). It commits at the end, which also persists the masked `raw`. If a filter matched, the flow returns here. Otherwise it returns early for canary signals or when `create_case` is false. Otherwise it creates a case (`case_service.create`), sets `signal_instance.case`, and starts the case, engagement, and workflow steps.

**Masking details (`redaction.py`)**

- `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` returns a copy. It lowercases and strips the configured field names, then recurses through dicts and lists at any depth.
- Matching is exact on the lowercased key, not substring. A value is replaced with `"[REDACTED]"` when its key matches. Values under non-matching keys are left alone, even if they look like secrets.
- Non-dict, non-list roots are returned unchanged.
- Defaults come from `config.py:98–102`: `SIGNAL_REDACTED_RAW_FIELDS`, default `"password,secret,api_key,session_token,authorization"`. It is overridable through the environment variable of the same name.
- Keys like `apiKey`, `x-api-key`, `token`, or `cookie` are not masked by default. They would need to be added to the env var to be covered. Note that `apiKey` lowercases to `apikey`, which does not equal `api_key`.

**Is the unmasked payload written to the database?**

Yes, in two places:

- **The gap:** `create_instance` commits the raw payload unmasked (`signal/service.py:680`, then the handler's commit). It stays unmasked until the processing loop runs. If the loop is not running, or the row is never picked up (it needs `filter_action` and `case_id` to be null), the unmasked payload stays in the `signal_instance.raw` JSONB column indefinitely.
- **Once processed:** the masked version overwrites the column when `filter_signal` commits. Entities derived from the masked payload are stored as well.

I did not run the tests or the app, and I made no code changes. I did not check whether the database column is encrypted at rest, what logs contain, or whether any API consumer reads `raw` back out of `SignalInstanceRead`. Those are the next checks if you want to know whether the gap is exposed.

----- next turn -----

The cause was commit `beb60cc4` ("perf(entity): stop at the first JSONPath match"). It changed `jpath.find(...)` to `jpath.find(...)[:1]` in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`). That slice keeps only one match per entity type, so a wildcard like `asset[*].id` produced one entity instead of one per field.

**Fix:** I reverted that line to `matches = jpath.find(signal_instance.raw)` and removed the comment the commit added. Nothing else changed, and I did not touch the tests.

**Verification:** `python -m pytest tests/entity` failed before the fix (`test_find_entities_with_field_only`: expected 2 entities, got 1). After the fix, all 11 tests pass.

The commit's performance goal is given up with this change. Each JSONPath is now fully evaluated, which is what the existing tests require. If you still want the speedup for single-value paths, that would need a different approach, such as only stopping early when the expression has no wildcards or multiple-match operators. I did not attempt that.

----- next turn -----

Instances of "GitHub: Personal access token exposed" were grouped because the masked token became an entity. The JSONPath for the token now matches the `"[REDACTED]"` string, so every instance produced the same entity value. The deduplication filter on that entity type then grouped them. I inferred this from the code. I did not read `filter_dedup` in full or reproduce it end to end.

**Fix** (`src/dispatch/entity/service.py`, `find_entities`):
- Entity extraction now runs on `redact_raw(signal_instance.raw)`, a masked copy of the payload.
- Any string match equal to `MASK` is skipped.

I put the guard in `find_entities` rather than only in the create flow. `entity_type/service.py:95` and `entity_type/flows.py:29` also call `find_entities` on stored instances. Those can still hold an unmasked payload if the processing loop has not run yet, so the flow-only fix would not have covered them. The masking in `signal/flows.py` is unchanged.

**Test** (`tests/entity/test_entity_service.py`): `test_find_entities_never_extracts_masked_values` puts a `session_token` into the payload and checks that no entity is created from it. It also checks that an unmasked value in the same payload still becomes an entity. I confirmed the new test fails without the fix.

**Verification:** `python -m pytest tests/entity tests/signal` gives 44 passed and 1 skipped. The skip was already there and I did not look into it.

One behavior change: a genuine value that is exactly the string `[REDACTED]` will no longer become an entity. I think that is acceptable, but say if you want it handled differently.

----- next turn -----

## Security review recap

**Request path.** `POST /api/v1/{organization}/signals/instances` (`src/dispatch/signal/views.py`) stores the payload with `signal_service.create_instance` and commits it. It does not run the processing flow. A background loop (`main_processing_loop` in `signal/flows.py`), the `dispatch signals process` CLI command, or the AWS plugin picks up unprocessed rows later. `signal_instance_create_flow` masks the payload, extracts entities, runs filters (`filter_signal`), and creates a case or stops at the filter.

**Masking.**
- `redact_raw` in `src/dispatch/signal/redaction.py` masks values under matching keys at any depth, including inside lists. Matching is exact on the lowercased key, not a substring.
- Defaults come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`. The default is `password,secret,api_key,session_token,authorization`, and it can be overridden through the environment variable.
- The flow masks the payload before entity extraction (`signal/flows.py:60`).

**Unmasked storage.** Yes. The POST handler commits the raw payload before any masking runs, so it sits unmasked in the `signal_instance.raw` column until the processing loop runs. It stays there if the row is never processed. Masking overwrites the column only when the filter step commits.

**Fixes made this session.**
1. **Extraction bug.** Commit `beb60cc4` added `[:1]` to the JSONPath match, so only the first match became an entity. I reverted it. `tests/entity` now passes (11 tests, then 12 with the new test).
2. **Masked values becoming entities.** The `[REDACTED]` string was being extracted as an entity, which grouped unrelated instances in dedup. `find_entities` now extracts from a redacted copy of the payload and skips any match equal to the mask. I added `test_find_entities_never_extracts_masked_values`, which fails without the fix. The masking in the flow is unchanged.

**Not verified.** I did not check whether the database column is encrypted at rest, what the logs contain, or whether API responses expose `raw`. I also inferred the dedup grouping from the code rather than reproducing it end to end.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95