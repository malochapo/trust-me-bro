Redaction does not happen while the POST request is handled. The API only stores the raw payload. Masking happens later, in a background processing loop, before entity extraction.

**The path**

1. **Route:** `POST /api/v1/{organization}/signals/instances` is `create_signal_instance` in `src/dispatch/signal/views.py:70`. The signals router is mounted at `/signals` in `src/dispatch/api.py:137`.
2. **Request handling:** the handler resolves the project and the signal definition (by external ID or variant, falling back to the default). It then calls `signal_service.create_instance` (`src/dispatch/signal/service.py:650`) and commits. `create_instance` copies `raw` and round-trips it through JSON, but does not mask anything. The row is saved with the unredacted payload. The handler accepts a `background_tasks` argument but never uses it.
3. **Processing loop:** the `dispatch signals process` command (`src/dispatch/cli.py:938`) runs `main_processing_loop` (`src/dispatch/signal/flows.py:441`). It fetches unprocessed instances in batches and calls `process_signal_batch` (`flows.py:~414`), which calls `signal_instance_create_flow`.
4. **Redaction:** `signal_instance_create_flow` (`src/dispatch/signal/flows.py:46`) runs `signal_instance.raw = redact_raw(signal_instance.raw)` at line 60. This comes before the `find_entities` call that extracts entities from the payload.
5. **Filter or case:** the flow then calls `signal_service.filter_signal`. If the instance is filtered, it returns there. Otherwise it goes on to canary handling, the `create_case` check, and case creation.

**The redaction function**

`redact_raw` in `src/dispatch/signal/redaction.py` returns a copy of `raw` with the value of every matching key replaced by `[REDACTED]`. Matching is case-insensitive and exact on the key name (not substring), at any depth within dicts and lists. The key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98`. It is configurable through that environment variable, and the default is `password,secret,api_key,session_token,authorization`.

**Consequence:** between the API write and the processing loop picking the instance up, the stored `raw` contains the unredacted values. Only the in-memory copy used for entity extraction and filtering is masked. I did not check whether every later code path that reads `raw` runs after this step.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no