## Recap

**Intake path.** `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `signal/views.py`. It resolves the signal definition and calls `signal_service.create_instance`. That call stores `raw` exactly as received, and the view commits it. The instance is returned to the caller unmasked. A worker later calls `signal_instance_create_flow`, from `process_signal_batch` or the `cli.py` consumer loop. The flow does the following:
1. It masks `raw`.
2. It extracts entities.
3. It runs the filters. A filtered instance stops there.
4. A canary, or a signal with `create_case` off, also stops there.
5. Otherwise it opens a case.

**Masking.** `redact_raw` in `signal/redaction.py` replaces the value of any key named in `SIGNAL_REDACTED_RAW_FIELDS` with `[REDACTED]`. It matches key names, not values. Matching is case-insensitive and exact, at any depth, inside dicts and lists. The defaults are `password`, `secret`, `api_key`, `session_token` and `authorization`. They can be overridden with the env var of the same name.

**Unmasked data in the database.** Yes. The raw payload is committed unmasked at request time. It is overwritten with the masked copy only when the worker processes the instance. If the worker never runs, the unmasked payload stays in the database.

**Extraction bug.** Commit `beb60cc4` added `[:1]` to `jpath.find(...)`, so only the first JSONPath match became an entity. I reverted that line, and `tests/entity` passes.

**Grouping bug.** Masking runs before entity extraction. A JSONPath pointing at the session token therefore returned `[REDACTED]` for every instance, and the deduplication filter grouped them all together. I fixed `find_entities` in `entity/service.py`. It now masks a copy of the payload and never turns a masked value into an entity. I added a test for it. The `tests/entity` and `tests/signal` suites pass.

**Unfixed.** `create_signal_instance` can raise `NameError` when the request supplies `signal`. The unmasked-at-intake behaviour is also still in place. I didn't change either.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4