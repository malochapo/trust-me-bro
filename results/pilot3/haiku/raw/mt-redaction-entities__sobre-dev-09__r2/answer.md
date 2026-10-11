## Security review recap

**Masking:** `redact_raw` in `src/dispatch/signal/redaction.py` replaces the value of any key in the configured list with `[REDACTED]`. It matches keys case-insensitively at any depth, including inside lists. It is called in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`), before entity extraction, filtering and case creation. The default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py`, which can be overridden by environment variable.

**Unmasked storage:** the `POST /api/v1/{organization}/signals/instances` handler (`src/dispatch/signal/views.py`) commits the raw payload before any masking happens. The masked version only replaces it when the background flow processes the instance, which runs on a loop roughly every 60 seconds. Instances that carry a client-supplied `filter_action` are never picked up by that loop, so their unmasked payload stays in the database.

**Changes this session (uncommitted, in the working tree):**
- `src/dispatch/entity/service.py`: removed the `[:1]` slice that limited extraction to the first JSONPath match. Also, `find_entities` now masks the payload itself and skips matches equal to `[REDACTED]`, so a masked value can never become an entity. This was the cause of the instances grouping into the same case.
- `tests/entity/test_entity_service.py`: added `test_find_entities_never_creates_entity_from_masked_value`. It fails on the original code and passes with the fix.

**Open items:**
- The uncommitted changes are not committed.
- `recalculate_entity_flow` in `src/dispatch/entity_type/flows.py` assigns `None` to `entity_types` by mistake. I did not touch it.
- The grouping mechanism is inferred from the code. I did not reproduce it end to end.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95