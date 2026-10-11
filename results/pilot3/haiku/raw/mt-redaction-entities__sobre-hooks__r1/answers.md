The unmasked payload is written to the database. It is committed in the POST handler, and the masked version only replaces it later, when the background processing loop picks the row up.

**Request path**

1. `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `src/dispatch/signal/views.py:70`. It resolves the project and the signal definition, then calls `signal_service.create_instance` and `db_session.commit()` (`views.py:~111-112`).
2. `signal_service.create_instance` (`src/dispatch/signal/service.py:650`) builds a `SignalInstance` from the request with `raw=json.loads(json.dumps(...))`. There is no masking here, and it only adds the row to the session.
3. The POST returns the instance, which includes `raw` (`SignalInstanceRead` inherits `raw` from the base model, `signal/models.py:394`). By my reading, the response echoes the unmasked payload. I did not run the endpoint to confirm this.
4. Nothing else runs in the request. The `background_tasks` parameter is unused.
5. Later, a processing loop finds rows with `filter_action IS NULL` and `case_id IS NULL` (`src/dispatch/signal/flows.py:385-428`, `process_organization_signals` and `process_signal_batch`, plus the similar loop in `src/dispatch/cli.py:~985-1010`). For each row it calls `signal_instance_create_flow` (`flows.py:46`) and then commits.
6. `signal_instance_create_flow` masks the payload at `flows.py:59-60`: `signal_instance.raw = redact_raw(signal_instance.raw)`. This runs before entity extraction, so entities are built from masked data.
7. Entity extraction (`entity_service.find_entities`) runs next, then `filter_signal` (`signal/service.py:866`, which commits at line 896). If the signal is filtered, the flow returns here, after redaction. If not, it goes on to create the case (`case_service.create`), engage the identity, and run workflows.

**Masking function**

- `redact_raw` in `src/dispatch/signal/redaction.py:10`. It returns a copy with values replaced by `"[REDACTED]"`. Matching is case-insensitive on exact dict keys, at any depth, including inside lists. Values that are not dicts or lists are returned unchanged.

**Default keys**

- `password`, `secret`, `api_key`, `session_token`, `authorization` (`src/dispatch/config.py:98-102`). Overridable with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable.
- Matching is exact, not substring. Keys such as `apiKey`, `api-key`, `token`, `access_token`, or `client_secret` are not masked by default.

**Is the unmasked payload written to the DB?**

Yes, in two places:

- **At POST time.** `create_instance` and the `db_session.commit()` in the view persist `raw` as received, before any redaction.
- **Until the loop processes the row.** The masked value overwrites the stored copy only when `process_signal_batch` gets to that row and commits. If processing fails before the commit, the unmasked payload stays in the table, and I'd expect the row to be retried. I inferred this from the exception handling and did not test it.

Filtered and deduplicated instances still go through redaction, because it runs before `filter_signal`. Only the window between insert and processing leaves the value unmasked.

**Other notes**

- There are no tests for redaction (`grep -rl redact tests` returns nothing).
- The AI prompt code reads `signal_instance.raw` directly (`src/dispatch/ai/service.py:212` and `:317`), and the Slack plugin attaches it as JSON (`src/dispatch/plugins/dispatch_slack/plugin.py:155`). Both read the stored value, so they see the masked copy only after processing.

I did not change any code.

----- next turn -----

The cause was commit `beb60cc4` ("perf(entity): stop at the first JSONPath match"). It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`, which keeps only the first match. Any entity type whose JSONPath matches several fields therefore produced one entity instead of one per field.

I removed the slice and its comment in `src/dispatch/entity/service.py` (about line 289), restoring `matches = jpath.find(signal_instance.raw)`. Nothing else changed, and no tests were edited.

Test results:
- `python -m pytest tests/entity`: before the fix, `test_find_entities_with_field_only` failed with `assert 1 == 2`. After the fix, all 11 pass.
- `python -m pytest tests/signal`: 32 passed, 1 skipped.

The fix is only the revert. The commit's "perf" goal is gone, so if you want a speedup for JSONPaths that match many fields, that needs a different change.

----- next turn -----

**Cause:** `find_entities` in `src/dispatch/entity/service.py` trusted whatever payload it was given. The signal flow masks the payload before calling it, but two other paths don't:

- `recalculate_entity_flow` (`entity_type/flows.py`) and the entity-type create path (`entity_type/service.py`, which runs for signal instances on a case) read the stored `raw`. Until a row is processed, that is the unmasked payload, so the session token became an entity there.
- Even when the flow does mask first, the JSONPath then matches `"[REDACTED]"`. Every instance of the signal gets an entity with that same value, and the dedup filter groups them into one case.

I haven't confirmed the second point against production data. It follows from the code, and it matches the report.

**Fix** (`src/dispatch/entity/service.py`):
- `find_entities` now runs `redact_raw` on `signal_instance.raw` itself, so every caller is covered. The masking in `redaction.py` and the existing call in the flow are unchanged.
- The JSONPath loop skips any match whose value is `MASK`. Masked values are always exactly `"[REDACTED]"`, so this catches them.

**Test:** `test_find_entities_never_extracts_masked_values` in `tests/entity/test_entity_service.py`, appended without changing existing tests. It sets `session_token` and `user` in the payload, uses a wildcard JSONPath, and asserts only `"alice"` becomes an entity. With the guard removed, the test fails. With it restored, `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**Trade-off:** a non-sensitive field whose value is literally `"[REDACTED]"` is also skipped. I judged that acceptable.

Nothing is committed. The change to `entity/service.py` from the previous fix (removing `[:1]`) and this change are both uncommitted in that file.

----- next turn -----

## Security review recap

**Trace of `POST /api/v1/{organization}/signals/instances`**

1. `create_signal_instance` (`src/dispatch/signal/views.py:70`) resolves the project and signal definition, then calls `signal_service.create_instance` and commits. The payload is stored as received, with no masking.
2. The response returns the instance with its unmasked `raw`, based on the response model. I did not run the endpoint to confirm this.
3. A background processing loop (`signal/flows.py:385-428`, plus a similar loop in `cli.py`) picks up rows with no `filter_action` and no `case_id`. For each one, `signal_instance_create_flow` (`flows.py:46`) masks `raw` at line 60, then runs entity extraction, then the filter, then case creation and workflows.
4. Masking happens before entity extraction and filtering, so filtered instances are masked too.

**Masking**

- `redact_raw` replaces the value of any matching key with `"[REDACTED]"`. Matching is case-insensitive on exact key names, at any depth, including inside lists.
- Defaults come from `SIGNAL_REDACTED_RAW_FIELDS` (`config.py:98-102`) and can be overridden by that environment variable. Matching is exact, so `apiKey`, `api-key`, `token`, and `access_token` are not masked by default.

**Fixes made this session**

- **Entity extraction (`beb60cc4`):** the commit added `[:1]` to the JSONPath match, so only the first match became an entity. I removed it. `tests/entity` passes (11 passed before the masking test was added).
- **Masked values as entities:** `recalculate_entity_flow` and the entity-type create path extract entities from the stored `raw`, which is unmasked until processing runs. A masked field then became the entity value `"[REDACTED]"`, and unrelated instances were grouped by the dedup filter. `find_entities` now masks the payload itself and skips any match equal to `MASK`. `redaction.py` is unchanged. I added `test_find_entities_never_extracts_masked_values`. It fails without the guard and passes with it. `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).
- Trade-off: a non-sensitive field whose value is literally `"[REDACTED]"` is also skipped.

**Open items**

- Nothing is committed. The two fixes are uncommitted changes to `src/dispatch/entity/service.py`, plus the new test.
- Unmasked payloads are stored between POST and processing. If processing fails before its commit, the unmasked payload may remain in the table. I inferred this from the exception handling and did not test it.
- The signal "GitHub: Personal access token exposed" report is explained by the masked-value grouping, but I did not check it against production data.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95