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