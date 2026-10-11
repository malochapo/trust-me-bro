The short answer is that redaction does not happen during the API request. The POST handler stores the raw payload as sent, and a background loop masks it later, before entity extraction and filtering.

**Trace**

1. **Request handling (synchronous):** `create_signal_instance` in `src/dispatch/signal/views.py:70-120` resolves the project and signal definition, then calls `signal_service.create_instance`. That function (`src/dispatch/signal/service.py:650-712`) copies `raw`, round-trips it through JSON, adds the `SignalInstance` to the session, and returns. The view commits and responds. No redaction happens here, so the raw payload is stored unmasked at this point.

2. **Background processing (asynchronous):** `main_processing_loop` in `src/dispatch/signal/flows.py` runs per organization every `LOOP_DELAY` seconds. `process_organization_signals` gets unprocessed instance IDs and calls `process_signal_batch`, which calls `signal_instance_create_flow`.

3. **Redaction:** `signal_instance_create_flow` (`src/dispatch/signal/flows.py`, around line 60) runs `signal_instance.raw = redact_raw(signal_instance.raw)` before any entity lookup. The comment there says "mask sensitive values before entities are extracted from the payload."

4. **Entity extraction:** `entity_service.find_entities` runs on the already-masked raw data.

5. **Filtering:** `signal_service.filter_signal` checks snooze and deduplication. If it filters the instance, the flow returns there.

6. **Case creation:** Canary signals and signals with `create_case` false return early. Otherwise the flow creates or attaches a case.

**Redaction function and defaults**

- `redact_raw` in `src/dispatch/signal/redaction.py` returns a copy of `raw`. Keys match case-insensitively at any depth, inside dicts and lists, and the value is replaced with `[REDACTED]`.
- The default key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98-102`, and it can be overridden with that environment variable.

**Caveat:** the raw payload sits unredacted in the database from the moment the POST commits until the processing loop runs. Redaction only applies to what the flow writes back and to downstream entity extraction and case creation.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no