The masking happens in the background processing step, not in the POST handler, and the unmasked payload **is** written to the database first. I made no code changes.

## Flow from POST to case or filter

1. **Route** `create_signal_instance` (`src/dispatch/signal/views.py:70`). It resolves the project, then the signal definition by `externalId` or `variant` from the raw payload, falling back to the project default. If none exists it returns 404.
2. **Instance build** `signal_service.create_instance` (`src/dispatch/signal/service.py:650`). It builds a `SignalInstance` with `raw=json.loads(json.dumps(...))`, a JSON round-trip only, so the payload is unmasked. It is added to the session but not yet committed.
3. **Commit in the view** (`views.py`, right after `create_instance`). This writes the **unmasked** `raw` to the `signal_instance.raw` JSONB column (`models.py:239`). The response is `SignalInstanceRead`, which has no `raw` field (`models.py:389-412`), so the payload isn't echoed back.
4. **Background processing.** The instance sits with `filter_action` and `case_id` unset until `process_signal_batch` (`src/dispatch/signal/flows.py:385`) calls `signal_instance_create_flow` (`flows.py:46`). That happens via `process_organization_signals` (`flows.py:406`) or the `signals process` CLI command (`src/dispatch/cli.py:937`, which calls the flow at `cli.py:1004`). I could not find an in-repo caller for `main_processing_loop` (`flows.py:441`).
5. **Masking** at `flows.py:60`: `signal_instance.raw = redact_raw(signal_instance.raw)`. This runs before entity extraction, so entity matching sees masked values.
6. **Entities.** If any entity types apply, `find_entities` runs and the session commits (`flows.py` ~line 75). The masked `raw` is persisted here.
7. **Filter** `signal_service.filter_signal` (`service.py:866`). It runs snooze and dedup, sets `filter_action`, and commits. If filtered, the flow returns with no case.
8. **Canary / no case.** Canary instances, and signals with `create_case` off, return here.
9. **Open case.** The flow resolves case type, priority, severity, and oncall assignee, then calls `case_service.create` and commits. It then runs `case_flows.case_new_create_flow`, engagements (if entities exist), and workflows.

## Masking function and defaults

- **Function:** `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` in `src/dispatch/signal/redaction.py`. It returns a copy and recurses through dicts and lists. Values under matching keys become `"[REDACTED]"`.
- **Matching:** case-insensitive exact key equality at any depth. It does not match substrings, and it does not normalise `-` vs `_`.
- **Default keys:** `password,secret,api_key,session_token,authorization` (`src/dispatch/config.py:98-102`), overridable via the `SIGNAL_REDACTED_RAW_FIELDS` env var.
- **Consequence:** `apiKey`, `x-api-key`, `token`, and `access_token` are not masked by default.

## Is the unmasked payload written to the database?

**Yes, in two places:**

- **Before masking, at step 3.** Every instance is committed unmasked by the POST handler. Instances that are never processed (for example, if the processing command isn't running) keep the raw value unmasked indefinitely.
- **Via `update_instance`** (`service.py:726`). It writes `raw` with no masking. I found no callers in `src/`, so it is currently dead code, but it is a second unmasked write path if it is ever wired up.

After `redact_raw` runs, the masked copy overwrites the column at the next commit. So masked data is only stored once processing has run. Both `redact_raw` and `create_instance` use `copy` or a round-trip and do not mutate the request object.

Related: `ai/service.py:317` interpolates `str(signal_instance.raw)` into the LLM prompt, and `ai/service.py:212` includes historical alert `raw` data. The LLM prompt is built from the in-memory masked payload when called from the flow. The historical case data is read from the DB and is masked only if that instance has already been processed.

I did not run tests or execute the endpoint. These findings come from reading the code.

----- next turn -----

The regression came from commit `beb60cc4` ("perf(entity): stop at the first JSONPath match"). I reverted its one-line change in `src/dispatch/entity/service.py`, and the entity tests now pass.

**Cause:** the commit changed `_find_entities_by_jsonpath_expression` to `jpath.find(signal_instance.raw)[:1]`. Its comment said a JSONPath "names one field", which isn't true for paths that match several values, such as wildcards or recursive descent. Only the first match became an entity.

**Fix:** I removed the `[:1]` slice and the comment, so the line is `matches = jpath.find(signal_instance.raw)` again. The diff is the only change in the working tree.

**Verification:**
- Before the fix, `tests/entity` failed: `test_find_entities_with_field_only` got 1 entity where it expects 2.
- After the fix, `python -m pytest tests/entity` passes (11 passed).
- `python -m pytest tests/signal tests/entity` passes (43 passed, 1 skipped).

**Trade-off:** the commit's stated goal was performance. Stopping at the first match saved work on paths with many matches, and this revert gives that up. If you want that saving back, it needs a different approach that still returns all matches, such as limiting only paths that can match at most one value. I didn't attempt that. I didn't change any tests.

I have not committed the change.

----- next turn -----

Masked values no longer become entities, so the dedup filter stops grouping unrelated instances under a shared `[REDACTED]` entity. Masking is unchanged.

**Cause:** the redaction step replaces the value under a masked key with the string `"[REDACTED]"`. The JSONPath extractor accepted any string, so an entity type pointing at `session_token` produced an entity with value `[REDACTED]` for every instance. The dedup filter on that entity type then matched all of them into one case.

**Fix** (`src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression`): a match is only turned into an entity if it is a string and not equal to `MASK`. I imported `MASK` from `dispatch.signal.redaction` so the two can't drift apart. This is the only extractor in the codebase. The regex path is compiled but never applied, so it has no extraction code to guard. Because the guard sits in `find_entities`, it also covers the historical-recalculation paths in `entity_type/service.py` and `entity_type/flows.py`.

**Test:** `test_find_entities_ignores_masked_values` in `tests/entity/test_entity_service.py`. It checks that masked session tokens produce no entities, and that an unmasked value under the same JSONPath still produces one. I confirmed it fails with the fix stashed and passes with it applied. I didn't change any existing tests.

**Verification:** `python -m pytest tests/entity tests/signal tests/entity_type` passes (50 passed, 1 skipped).

**Not done:** entities already created from `[REDACTED]` in the database are still there, and the cases grouped under them stay grouped. Cleaning those up needs a data decision from you (delete the `[REDACTED]` entities and re-run extraction, or leave them), so I haven't touched the data. I also haven't committed anything.

----- next turn -----

Here's the recap for the security review. Nothing is committed yet: the entity-extraction fix and the new test are uncommitted working-tree changes.

**Masking of the raw payload**
- Masking happens in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`), before entity extraction. The view's POST handler does not mask anything.
- Matching is case-insensitive exact key equality at any depth, through dicts and lists. Substrings and `-` vs `_` variants are not matched, so `apiKey` and `x-api-key` are not masked by default.
- The unmasked payload is written to the database by the POST handler's commit, before the background flow runs. Instances that are never processed keep it unmasked. The masked copy overwrites it at the next commit in the flow.
- `update_instance` (`src/dispatch/signal/service.py:726`) also writes `raw` without masking. Nothing in `src/` calls it today.

**Entity extraction**
- `beb60cc4` added `[:1]` to the JSONPath match, so only the first match became an entity. That broke `test_find_entities_with_field_only`. I reverted it.
- Masked values were becoming entities: every instance shared the value `[REDACTED]`, and the dedup filter grouped them. I fixed this in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`) by skipping values equal to `MASK`. I added `test_find_entities_ignores_masked_values`, which fails without the fix and passes with it.
- Entities already created from `[REDACTED]` remain in the database. Deleting them and re-running extraction needs a data decision, so I haven't done it.

Verification: `python -m pytest tests/entity tests/signal tests/entity_type` passes (50 passed, 1 skipped).

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95