The short answer is that redaction runs in the background processing loop, not in the POST handler. The API request only stores the raw payload unredacted, and a separate worker later masks it and creates the case.

**Trace**

1. **API handler** (`src/dispatch/signal/views.py:70-120`, `create_signal_instance`). It resolves the project and signal definition, then calls `signal_service.create_instance` and commits. It does not call any redaction code, and it does not queue `signal_instance_create_flow` as a background task. The response returns the instance with its raw payload still unredacted.

2. **Storage** (`src/dispatch/signal/service.py:650-680`, `create_instance`). It copies `raw`, drops `oncall_service` if present, round-trips it through JSON, and inserts the `SignalInstance` row. No masking happens here.

3. **Async processing.** The instance is picked up later by `main_processing_loop` in `src/dispatch/signal/flows.py` (around line 441), which calls `process_organization_signals` and then `process_signal_batch` (line 385). `process_signal_batch` calls `signal_instance_create_flow` for each ID and commits. The same flow is also invoked from `src/dispatch/cli.py:1004`.

4. **Redaction** (`src/dispatch/signal/flows.py:59-60`). `signal_instance_create_flow` sets `signal_instance.raw = redact_raw(signal_instance.raw)` with the comment "mask sensitive values before entities are extracted from the payload". That reassignment is then persisted when the batch commits.

5. **Entity extraction** (`flows.py:63-72`). Entity types are gathered and `entity_service.find_entities` runs on the already-redacted raw.

6. **Filtering** (`flows.py:~80-104`). If the instance is filtered or deduplicated, it stops here.

7. **Case creation** (`flows.py:~153-210`). Otherwise `case_service.create` runs, followed by `case_flows.case_new_create_flow`.

**Redaction function** (`src/dispatch/signal/redaction.py`). `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` returns a copy with the value of any matching key replaced by `[REDACTED]`. Matching is case-insensitive and applies at any depth, through dicts and lists. The default list comes from `src/dispatch/config.py:98-102`, which reads the `SIGNAL_REDACTED_RAW_FIELDS` env var and falls back to `password,secret,api_key,session_token,authorization`.

**Caveat.** Because the raw payload is stored unredacted before the worker runs, the unredacted copy exists in the database until the processing loop commits. The API response also returns it unredacted. I did not check whether anything else reads `raw` between insert and processing.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no