## Security review recap

**Masking.** The payload is masked by `redact_raw` in `src/dispatch/signal/redaction.py`. It returns a copy in which any value under a listed key is replaced with `"[REDACTED]"`. Keys match case-insensitively at any depth, inside dicts and lists. The key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`, which can be overridden by environment variable. Matching is exact, so `token`, `client_secret`, `x-api-key`, and `apiKey` are not masked by default. The call site is `signal_instance_create_flow` in `src/dispatch/signal/flows.py:60`, which runs in the background processing loop, not during the API request.

**Unmasked payload in the database.** Yes. `create_signal_instance` in `src/dispatch/signal/views.py:120` commits the instance with the original `raw` before any masking runs. The masked version is only written when a later commit happens in the flow, so there is a window in which secrets are stored in plain text. If processing fails, the rollback leaves the unmasked payload in place. Rows the loop never reaches also keep it.

**Entity extraction leak (fixed this session).** The flow masks `raw` and then extracts entities from the masked copy. A JSONPath pointing at a masked field therefore produced an entity with the value `"[REDACTED]"`. Entities are deduplicated by value, so unrelated instances shared one entity, and the deduplication filter grouped them into one case. `find_entities` in `src/dispatch/entity/service.py` now redacts the payload itself and skips any match equal to the mask, so every extraction path is covered. A regression test is in `tests/entity/test_entity_service.py`. Existing `[REDACTED]` entities in the database are not cleaned up.

**Other changes this session.** Entity extraction was keeping only the first JSONPath match because of commit `beb60cc4`. I reverted that in `src/dispatch/entity/service.py`. The entity tests pass (12/12), and the signal tests pass (32 passed, 1 skipped). All changes are uncommitted in the working tree.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95