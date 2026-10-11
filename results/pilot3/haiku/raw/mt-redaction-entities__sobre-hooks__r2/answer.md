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