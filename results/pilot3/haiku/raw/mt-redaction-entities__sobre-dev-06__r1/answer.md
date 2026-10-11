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