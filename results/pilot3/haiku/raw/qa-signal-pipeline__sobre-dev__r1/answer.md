The redaction happens after the API request has returned, in the background processing loop, not in the POST handler.

**Trace**

1. **Route:** `POST /api/v1/{organization}/signals/instances` is `create_signal_instance` in `src/dispatch/signal/views.py:70-158`. It resolves the project and signal definition, then calls `signal_service.create_instance`. It commits and returns the instance. It never calls `redact_raw` or the create flow.
2. **Storage:** `signal_service.create_instance` (`src/dispatch/signal/service.py:650`) builds the `SignalInstance` with `raw` set to a JSON round-trip of the incoming payload. The payload is stored unredacted.
3. **Processing (later, not in the request):** `main_processing_loop` in `src/dispatch/signal/flows.py` calls `process_organization_signals` for each organization. That fetches unprocessed instance IDs and passes them to `process_signal_batch`, which calls `signal_instance_create_flow` (`flows.py:46`) and commits.
4. **Redaction:** the first step in `signal_instance_create_flow` is `signal_instance.raw = redact_raw(signal_instance.raw)`, with the comment "mask sensitive values before entities are extracted from the payload". Entity extraction (`entity_service.find_entities`) comes after this line.
5. **Filtering or case creation:** `signal_service.filter_signal` runs next. If it filters the instance, the flow returns early. Otherwise, the flow goes on to canary handling and `create_case`.

**Redaction details**

- `src/dispatch/signal/redaction.py`: `redact_raw` lowercases and strips the configured field names. `_redact` recurses through dicts and lists, at any depth, and replaces matching key values with `"[REDACTED]"`. Other values are unchanged.
- Default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98`: `password,secret,api_key,session_token,authorization`. The env var overrides this.

**Consequences**

- The API response (`SignalInstanceRead`) echoes the stored `raw`, which has not been redacted yet. Redaction only applies to the database record once the background loop processes it.
- Between the POST and processing, unredacted payloads sit in the database.
- The CLI path (`src/dispatch/cli.py:1004`) also calls the same create flow.

I did not check where `main_processing_loop` is started, so I can't say which process runs it. I also did not run the code or tests.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no