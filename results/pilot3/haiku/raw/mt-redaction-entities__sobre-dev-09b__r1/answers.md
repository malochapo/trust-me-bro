The unmasked payload is written to the database. The API commits the raw payload before any masking happens, and masking runs later, in a background loop. Nothing was changed.

**Request path**

1. **Route:** `POST /signals/instances` is `create_signal_instance` in `src/dispatch/signal/views.py:70-73`. It is rate-limited to 1000/minute. It resolves the project and the signal definition (by external id or variant, falling back to the default), then calls `signal_service.create_instance` and commits (`views.py:~119-121`).
2. **Storage:** `create_instance` in `src/dispatch/signal/service.py:~655-737` builds the `SignalInstance` with `raw=json.loads(json.dumps(...))`. That is only a JSON round-trip, with no masking. `db_session.commit()` runs right after it in the view, so the payload is in the database unmasked at that point. The endpoint then returns the instance.
3. **Background processing:** the endpoint never calls the flow. `background_tasks` is declared at `views.py:76` but never used. The flow runs from `signal_flows.main_processing_loop` (`src/dispatch/signal/flows.py:~442`), started by `dispatch signals process` (`cli.py:938`). Every 60 seconds it picks up instances with `filter_action IS NULL` and `case_id IS NULL`, in batches of 50 per organization (`flows.py:385-470`).
4. **Masking:** `signal_instance_create_flow` (`flows.py:46`) runs `signal_instance.raw = redact_raw(signal_instance.raw)` at `flows.py:60`, before entity extraction. This is the only call site of `redact_raw`.
5. **Entities:** `entity_service.find_entities` runs on the masked payload. If any entity types exist, it commits at `flows.py:75`.
6. **Filter or case:** `signal_service.filter_signal` (`service.py:866`) runs next. Snoozed or deduplicated instances return early (`flows.py:78-100`). Canary signals and signals with `create_case=False` also return early (`flows.py:103-107`). Otherwise `case_service.create` runs and the instance is committed (`flows.py:188-191`).
7. **Commit:** the flow itself does not commit on the filter path. The caller, `process_signal_batch` (`flows.py:~395`) or the loop in `cli.py:~1004`, commits after each instance. On an exception it rolls back.

**Masking function and defaults**

- Function: `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` in `src/dispatch/signal/redaction.py`. It returns a new structure and does not mutate the input. It recurses through dicts and lists. Any value whose key matches (after lowercasing) is replaced with `"[REDACTED]"`. Anything else is returned unchanged.
- Defaults (`src/dispatch/config.py:98-102`, overridable with the `SIGNAL_REDACTED_RAW_FIELDS` env var): `password`, `secret`, `api_key`, `session_token`, `authorization`.
- Matching is exact on the lowercased key, not substring. So `apiKey` (lowercased to `apikey`) does not match `api_key`, and `x-api-key` and `client_secret` do not match either. Only the top-level key name is compared against the set, so a nested key that happens to be named `password` is masked too.

**Is the unmasked payload written to the database?**

Yes, in two windows:

- **Between the API commit and the processing loop.** The raw payload is stored unmasked by the endpoint commit. It stays that way until the loop processes the instance, which can take up to about 60 seconds plus batching.
- **If processing fails.** The redaction only persists if the flow's commit succeeds. On an exception the loop rolls back, which also undoes the in-memory redaction. The instance is retried on the next pass because it still has no `filter_action` or `case_id`. If processing keeps failing, the unmasked payload stays in the database indefinitely.

After a successful run, the masked version is what gets committed.

**Things I did not verify**

- Whether the endpoint's response body (`SignalInstanceRead`) includes `raw`. If it does, the caller receives the unmasked payload in the HTTP response.
- Whether other code reads `raw` before the processing loop (for example notifications), or copies it elsewhere.
- Whether `update_instance` (`service.py:~728`) is reachable from any HTTP path. It writes `raw` unmasked, and I did not trace its callers.
- Test coverage: a grep of `tests/` for `redact` returned nothing, so I found no test of the masking behavior.

----- next turn -----

The cause was commit `beb60cc4` ("perf(entity): stop at the first JSONPath match"). It added `[:1]` to the JSONPath results in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`), so only the first match per entity type became an entity.

I reverted that line to `matches = jpath.find(signal_instance.raw)` and removed the comment that came with it. That is the only change in the working tree; the tests are untouched.

Results:
- `python -m pytest tests/entity`: 11 passed. Before the fix, `test_find_entities_with_field_only` failed with `assert 1 == 2`.
- `python -m pytest tests/signal`: 32 passed, 1 skipped. I ran this as a wider check because the signal flow depends on entity extraction.

The commit's "perf" intent is not preserved. Stopping at the first match changes which entities are produced, so the tests are right to reject it. If the goal is still a speedup, it needs a different approach that keeps all matches.

----- next turn -----

Masked values no longer become entities. The fix is in `find_entities` (`src/dispatch/entity/service.py`), which is the single extraction point for every caller.

**Why it happened**

- The signal flow masks `raw` first (`flows.py:60`), so a JSONPath aimed at `session_token` matches the string `"[REDACTED]"`.
- `find_entities` accepted that as a normal string value. Every instance then got the same `[REDACTED]` entity.
- The deduplication filter groups by entity value, so unrelated instances collapsed into one case.
- The entity-type create and recalculate paths (`entity_type/service.py:83-100`, `entity_type/flows.py:29`) call `find_entities` on stored `raw`. Stored `raw` is unmasked until the flow has processed the instance, so those paths could extract real secrets too.

**The fix**

- `find_entities` now runs `redact_raw` on a copy of `raw` before matching, using the same default fields. The masking in `flows.py` is unchanged.
- Any match whose value equals the mask sentinel is skipped.

**Test**

`test_find_entities_never_extracts_masked_values` in `tests/entity/test_entity_service.py` checks a top-level `session_token`, a nested `user.password`, and a normal `user.name`. Only `alice` comes back as an entity. Without the fix, the test fails; with it, it passes.

Results: `python -m pytest tests/entity tests/signal` gives 44 passed, 1 skipped.

**Edge case**

A payload field whose real value is the literal string `"[REDACTED]"` is also skipped as an entity. I accepted that, because the mask sentinel is the only signal available once the value has been masked.

----- next turn -----

Recap of the security review, covering the masking, the entity bug and the new test.

**Masking.** Sensitive values in the raw payload are masked in `redact_raw` (`src/dispatch/signal/redaction.py`). It replaces the value of any key whose lowercased name is in the configured set, at any depth in dicts and lists, with `[REDACTED]`. The default set is `password`, `secret`, `api_key`, `session_token` and `authorization`, set in `src/dispatch/config.py`. Matching is exact on the key name, so `apiKey` and `x-api-key` are not masked. The flow calls it in `signal_instance_create_flow` before entity extraction.

**Database exposure.** The unmasked payload is written to the database. `POST /signals/instances` commits the raw payload before any processing. The masked version is only written after the background loop processes the instance successfully, and a failed run rolls the masking back. If processing keeps failing, the unmasked payload stays in place.

**Entity bug.** Commit `beb60cc4` added `[:1]` to the JSONPath matches, so only the first match became an entity. I reverted that line in `src/dispatch/entity/service.py`. `tests/entity` now passes, 11 tests.

**Masked values as entities.** A JSONPath aimed at a masked field matched the `[REDACTED]` string, which then became an entity. Analysts reported unrelated instances grouped into one case through the deduplication filter. `find_entities` now masks its own copy of the payload and skips any match equal to the mask. I added `test_find_entities_never_extracts_masked_values`, which fails without the fix. Because `find_entities` is the single extraction point, the fix also covers entity-type creation and recalculation, which can read unprocessed raw. Payloads whose real value is the literal `[REDACTED]` are skipped as well.

**Status.** The changes are uncommitted in the working tree. I have not committed or pushed. `tests/entity` and `tests/signal` pass, 44 passed and 1 skipped.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95