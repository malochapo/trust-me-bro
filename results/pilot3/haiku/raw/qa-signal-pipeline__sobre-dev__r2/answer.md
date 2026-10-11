The POST handler does not redact the payload. Redaction runs later, in a background processing step, so the raw payload is stored unredacted at insert time.

**1. The POST request (`src/dispatch/signal/views.py:70-120`, `create_signal_instance`)**
- It resolves the project and the signal definition (by external ID or variant, falling back to the default).
- It calls `signal_service.create_instance`, which builds the `SignalInstance` and stores `raw` after only a JSON round-trip (`src/dispatch/signal/service.py:650-690`). No redaction happens here.
- It commits and returns `SignalInstanceRead`, which includes `raw` (`models.py:394`). The response therefore echoes the unredacted payload.
- The handler declares `BackgroundTasks` but never adds a task, so no processing is queued from the request.

**2. Redaction (`src/dispatch/signal/flows.py:46-60`, `signal_instance_create_flow`)**
- The flow loads the instance and runs `signal_instance.raw = redact_raw(signal_instance.raw)` before entity extraction. The comment says so explicitly.
- `redact_raw` in `src/dispatch/signal/redaction.py` lowercases the key names, then replaces matching values with `[REDACTED]` at any depth inside dicts and lists. It matches whole key names, not substrings, so `password` does not match `user_password`.
- Default keys come from `src/dispatch/config.py:98-102`: `password, secret, api_key, session_token, authorization`. The `SIGNAL_REDACTED_RAW_FIELDS` environment variable overrides them.

**3. Entity extraction and filtering (same flow)**
- Entity extraction runs on the redacted `raw` (`flows.py:63-75`), so values under redacted keys cannot become entities.
- `signal_service.filter_signal` runs next (`flows.py:78`). It applies snooze and deduplication, and a filtered instance returns early. Redaction happens before this step, so filtered instances are redacted too.
- If the instance is not filtered, the flow continues to case creation. That part is outside the scope of this trace.

**4. What invokes the flow**
- `process_signal_batch` (`flows.py:385-403`) is called from `process_organization_signals` (`flows.py:406-438`). That is reached from `main_processing_loop` (`flows.py:441`), which has no caller in this repo.
- A separate CLI path in `src/dispatch/cli.py` (around line 990-1010) picks up up to 500 instances with no `filter_action` and no `case_id`, and calls the same flow.
- Each instance is committed after the flow, so the redacted `raw` is persisted at that point.

**Consequence:** between the POST and the processing run, the database and the POST response both hold the unredacted payload, including keys like `password` or `authorization`. Redaction only applies to the stored record once the flow processes it. If you need the sensitive values kept out of the database or the response, the redaction would have to move into `create_instance` or the handler.

I did not run the code or the tests. The trace is from reading the source.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no