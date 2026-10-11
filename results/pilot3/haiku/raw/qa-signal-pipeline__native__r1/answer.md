The redaction happens in a background pass, not while the POST is handled. The request only stores the raw payload unredacted, and the masking runs later in the signal processing loop.

**Trace**

1. **Route:** `POST /api/v1/{organization}/signals/instances` is `create_signal_instance` in `src/dispatch/signal/views.py:70-118`. It resolves the project and signal definition, then calls `signal_service.create_instance(...)` and commits. It returns the new instance.

2. **Storage:** `create_instance` in `src/dispatch/signal/service.py:650` copies `raw`, drops `oncall_service` if set, and round-trips it through JSON. It does not touch sensitive keys. The instance is saved with its raw payload intact.

3. **Background processing:** `process_organization_signals` (`src/dispatch/signal/flows.py:~410`) fetches unprocessed instances via `get_unprocessed_signal_instance_ids` (`service.py:900`) and runs them in batches through `process_signal_batch` (`flows.py:385`). That is driven by the `signals process` CLI loop (`src/dispatch/cli.py:938`).

4. **Redaction:** `signal_instance_create_flow` (`flows.py:46`) runs first on each instance. Its line 59-60 says "mask sensitive values before entities are extracted from the payload" and then does `signal_instance.raw = redact_raw(signal_instance.raw)`. `redact_raw` lives in `src/dispatch/signal/redaction.py`. It walks dicts and lists recursively, matches keys case-insensitively at any depth, and replaces matching values with `[REDACTED]`.

5. **Default keys:** `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98` defaults to `password,secret,api_key,session_token,authorization`. It can be overridden through the environment variable of the same name.

6. **Entity extraction:** Entity extraction comes right after redaction (`flows.py:~63-75`), so extracted entities see the masked payload.

7. **Filtering or case creation:** `signal_service.filter_signal` (`service.py:866`) runs next. If it filters the instance, the flow returns early. Otherwise canary and `create_case` checks decide whether a case is opened.

**Caveat:** Between the POST and the background pass, the database holds the unredacted payload. Any code that reads `SignalInstance.raw` in that window sees the secrets. I did not check whether anything does. Also, matching is exact after lowercasing, so a key like `api-key` would not be masked by the default `api_key` entry.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no