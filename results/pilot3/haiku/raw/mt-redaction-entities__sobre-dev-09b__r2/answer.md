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