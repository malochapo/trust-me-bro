A signal instance is stored unredacted by the API request, and the redaction runs later in a background loop.

**Trace**

1. **API request.** `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `src/dispatch/signal/views.py:72`.
   - It resolves the project.
   - It looks up the signal definition by `externalId` or `variant` in `raw`, falls back to the project's default definition, and returns 404 if there is none.
   - It calls `signal_service.create_instance(...)` and commits. A duplicate id gives 409.
   - It returns the instance. There is no redaction and no entity extraction in this path.
2. **Background processing.** `main_processing_loop` in `signal/flows.py:441` sleeps 60 seconds between passes.
   - `process_organization_signals` loads the unprocessed signal instance ids for each organization.
   - It passes them in batches to `process_signal_batch`, which calls `signal_instance_create_flow` (`flows.py:46`) for each id.
3. **Inside `signal_instance_create_flow`:**
   - Line 60 runs `signal_instance.raw = redact_raw(signal_instance.raw)`.
   - Lines 63–75 then find entities in the payload. This is the entity extraction, so redaction comes first.
   - Line 78 calls `signal_service.filter_signal`. If a filter acts (for example deduplicate or snooze), the flow returns there. For a deduplicated instance with an existing case it may update the Slack signal message.
   - It also returns without a case for canary signals and for signals with `create_case` off.
   - Otherwise it goes on to open a case, using the case type, priority, on-call service and conversation target taken from the instance, then the signal, then the case type.

**Redaction**

`redact_raw` is in `src/dispatch/signal/redaction.py`. It returns a copy of the payload in which any key named in the list has its value replaced with `[REDACTED]`. Keys match case-insensitively, at any depth, inside dicts and lists.

The default key list is `SIGNAL_REDACTED_RAW_FIELDS` in `dispatch/config.py:98`. The `SIGNAL_REDACTED_RAW_FIELDS` environment variable can override it. The default is `password,secret,api_key,session_token,authorization`.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no