**Short answer:** Masking happens in `redact_raw` (`src/dispatch/signal/redaction.py`), called from `signal_instance_create_flow`. It is not in the API handler. The default masked keys are `password, secret, api_key, session_token, authorization`. The unmasked payload is written to the database during the API request, before any masking runs, and the response also returns it unmasked.

I made no code changes.

**Path from the request to a case or filter**

1. **Handler:** `create_signal_instance` in `src/dispatch/signal/views.py:70-115`. It resolves the project, then the signal definition (by `externalId`/`variant` from `raw`, falling back to the default). It calls `signal_service.create_instance` and then `db_session.commit()`, and returns the instance. It never calls the flow, and the `background_tasks` argument is unused.
2. **Persist:** `create_instance` in `src/dispatch/signal/service.py:650-716` copies `raw`, JSON round-trips it, builds a `SignalInstance`, and `db_session.add`s it (`service.py:666-683`, `:716`). The `raw` column is `JSONB` (`signal/models.py:239`). Nothing is masked here.
3. **Processing (asynchronous):** The flow runs later, in the `signals process` CLI loop (`src/dispatch/cli.py:937`, which selects rows with `filter_action` and `case_id` both null, up to 500 per pass) or `main_processing_loop` / `process_organization_signals` (`signal/flows.py:406-468`). Both call `signal_instance_create_flow` (`signal/flows.py:46`).
4. **Masking:** `signal_instance_create_flow` runs `signal_instance.raw = redact_raw(signal_instance.raw)` at `signal/flows.py:59-60`. This is before entity extraction (`entity_service.find_entities`, which reads `raw` via JSONPath at `entity/service.py:290`) and before filtering.
5. **Entities and filtering:** Entities are extracted and committed if any entity types apply (`flows.py:63-75`). Then `signal_service.filter_signal` (`service.py:866-897`) runs snooze and dedup. It always commits and sets `filter_action` to `none` or the filter action.
6. **Outcome:** If filtered, the flow returns early (`flows.py:77-97`). Canary instances return early (`:101`). If `signal.create_case` is false, the flow returns early (`:104`). Otherwise it creates a case, sets `signal_instance.case`, commits, starts the case flow, runs engagements, and runs workflows (`:105-226`).

**Masking function and defaults**

- `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` returns a copy (`redaction.py`). Field names are stripped and lowercased, and key matching is case-insensitive.
- Matching is on exact key names, at any depth, in dicts and in lists. Any value under a matching key is replaced with `"[REDACTED]"`, whatever its type. Strings elsewhere are not scanned.
- Defaults come from `src/dispatch/config.py:98-102`: `password,secret,api_key,session_token,authorization`. Override with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable (comma-separated).
- Because matching is exact, `apiKey`, `client_secret`, `x-api-key`, and `access_token` are not masked by default. Note that `apiKey` with no underscore is not matched, because `api_key` must equal the key after lowercasing.

**Is the unmasked payload written to the database?**

Yes. Two places:

- **At request time:** `create_instance` stores the raw payload and the view commits it (`service.py:666-683`, `views.py:98`). Until the background flow runs, the stored `raw` is unmasked. The same column is overwritten with the masked copy later, so the unmasked value is not kept separately after processing.
- **If processing fails:** Masking is only in memory until a commit. If `find_entities` or `filter_signal` raises, `process_signal_batch` (`flows.py:385-403`) or the CLI loop (`cli.py:~985-1010`) rolls back. The masking is discarded and the row keeps the unmasked payload. The instance is retried on the next pass, and the unmasked data stays in the row while it fails. This is inferred from the code and I did not run it.

Also, the `SignalInstanceRead` response model includes `raw` (`signal/models.py:394`, `:408`). The view returns the instance before the flow runs, so the HTTP response also contains the unmasked payload.

**Gaps I did not check**

- `signal_service.update_instance` (`service.py:722-738`) writes `raw` without masking. I found no callers for it in `src/`, so it looks unused, but I did not check the whole repo.
- The AWS plugin path (`plugins/dispatch_aws/plugin.py:113`) calls a different `create_signal_instance` (`service.py:162`). I did not trace whether it reaches the redaction flow.
- The `signals consume` command (`cli.py:879`) and any tests for `redact_raw` were not read.

----- next turn -----

The regression came from commit `beb60cc4` ("perf(entity): stop at the first JSONPath match", Sam Ortega, Sep 2). It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`, so each entity type's JSONPath contributed only its first match. I reverted that one line to `matches = jpath.find(signal_instance.raw)`. I did not touch any tests.

`python -m pytest tests/entity -q` now gives 11 passed against the local PostgreSQL.

I did not run the test against the broken code to confirm it failed there, so the link between this line and the red CI is from reading the diff, not from a failing run. The change is the only diff in the working tree, and it is uncommitted. The `[:1]` was a perf optimization. If you want the speedup back, it would need a different approach that still returns every match.

----- next turn -----

The cause: the flow masks the payload in memory, so a JSONPath aimed at the session token matched the string `"[REDACTED]"`. Every instance of that signal therefore got the same entity, and the dedup filter on that entity grouped them into one case. The masking itself is unchanged.

**Fix (`src/dispatch/entity/service.py`)**
- `find_entities` now matches against `redact_raw(signal_instance.raw)`, so entity extraction never sees the real secret. It also skips any match whose value is the mask. This is inside `find_entities`, so it covers both callers: the signal flow and `entity_type/service.py:95`, which re-extracts from stored payloads that may not have been masked yet.
- The helper takes the redacted `raw` as an argument and skips matches equal to `MASK`.

**Test (`tests/entity/test_entity_service.py`)**
- Added `test_find_entities_never_creates_entity_from_masked_value`. Two instances with different `session_token` values must produce no entities, and none may carry the mask. I didn't modify the existing tests.
- The new test fails without the fix and passes with it.

**Results**
- `python -m pytest tests/signal tests/entity tests/entity_type -q`: 50 passed, 1 skipped.

Changes are uncommitted in the working tree. Two limits on what I checked:
- The skip-on-mask rule also drops a payload value that is literally the string `"[REDACTED]"`. That is not a real secret, so I left it.
- The fix covers only JSONPath extraction. The entity-type code has no regex extraction in `find_entities` at present, so I didn't change anything there.

----- next turn -----

## Recap

**Masking.** The payload is masked by `redact_raw` in `src/dispatch/signal/redaction.py`. It is called from `signal_instance_create_flow` (`src/dispatch/signal/flows.py:59-60`) before entity extraction and filtering. Matching is case-insensitive on exact key names, at any depth, inside dicts and lists. The default keys are set in `src/dispatch/config.py:98-102` and can be overridden with `SIGNAL_REDACTED_RAW_FIELDS`. I did not change the masking.

**Unmasked data in the database.** Yes. `POST /api/v1/{organization}/signals/instances` stores the raw payload unmasked and commits it in the request (`signal/service.py:create_instance`, `signal/views.py`). The response also returns it unmasked. Masking only happens later, in the processing flow. If that flow fails, the rollback discards the in-memory masking and the unmasked payload stays in the row, and the flow retries it. I found this by reading the code; I did not run the failure case.

**Entity extraction bug.** Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath matches in `find_entities`, so only the first match per entity type became an entity. I reverted that line. `tests/entity` passed afterward. I did not run the test against the broken code, so the link to the red CI comes from the diff.

**Masked values as entities.** This was a second bug. The flow masks the payload before entity extraction, so a JSONPath aimed at a masked key matched `"[REDACTED]"`. Every such instance got the same entity, and the dedup filter grouped them into one case. The fix is in `find_entities` (`src/dispatch/entity/service.py`). It matches against the redacted payload and skips any match equal to the mask. It covers the flow and the entity-type re-extraction path (`entity_type/service.py:95`). I added `test_find_entities_never_creates_entity_from_masked_value`. It fails without the fix and passes with it. `tests/signal`, `tests/entity`, and `tests/entity_type` pass: 50 passed, 1 skipped.

**Open items**
- The fixes are uncommitted in the working tree.
- The skip-on-mask rule also drops a payload value that is literally `"[REDACTED]"`. That is not a secret, so I accepted it.
- Not yet examined: `signal_service.update_instance` writes `raw` without masking. I found no callers in `src/`. The AWS plugin path (`plugins/dispatch_aws/plugin.py`) was not traced.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95