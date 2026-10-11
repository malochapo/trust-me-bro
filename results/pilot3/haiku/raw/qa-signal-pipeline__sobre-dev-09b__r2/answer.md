**Flow for `POST /api/v1/{organization}/signals/instances`:**

1. **API handler (`dispatch.signal.views.create_signal_instance`, `src/dispatch/signal/views.py:70`)** resolves the project and the signal definition, then calls `signal_service.create_instance` and commits. It returns the new instance. It never calls the redaction code. The `background_tasks` parameter is declared but not used in the code I read.

2. **Processing, later and outside the request:** `dispatch.signal.flows.signal_instance_create_flow` (`src/dispatch/signal/flows.py:46`) loads the stored instance by id. Its callers are a processing loop in `src/dispatch/cli.py` (around line 1004), which picks up unprocessed instances in batches, and `process_signal_batch` (`flows.py:385`, called at `flows.py:428`).

3. **Redaction (`flows.py:60`):** `signal_instance.raw = redact_raw(signal_instance.raw)`. This runs before entity extraction at `flows.py:66–74` (`entity_service.find_entities`). The function is `dispatch.signal.redaction.redact_raw`. It matches keys case-insensitively at any depth inside dicts and lists and replaces their values with `[REDACTED]`.

4. **Filtering and case creation:** after redaction and entity extraction, `signal_service.filter_signal` decides whether the instance is filtered (deduplicated, etc.). If it isn't, the flow goes on to create a case, unless the signal is canary or has `create_case` disabled.

**Default keys:** `password,secret,api_key,session_token,authorization`, defined as `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98`. They can be overridden with the `SIGNAL_REDACTED_RAW_FIELDS` environment variable.

**Caveat:** I did not read `signal_service.create_instance` in full. Redaction only happens in the later flow, so the raw payload is presumably persisted unredacted at POST time, and the masked copy is written only when the flow runs and commits. I inferred that from the code order, not from a test.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no