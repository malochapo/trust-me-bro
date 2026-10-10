Redaction does not happen while the API request is handled. It happens later, in the background signal-processing flow, and it runs before entity extraction and filtering.

**Trace**

1. **API request.** `POST /instances` is `create_signal_instance` in `src/dispatch/signal/views.py:72`.
   - It resolves the project and the signal definition. It looks the definition up by `externalId` or `variant` in `raw`, then falls back to the project's default definition.
   - It then calls `signal_service.create_instance` (`signal/service.py:650`), which copies `raw` with `json.loads(json.dumps(...))` and builds the `SignalInstance`.
   - `views.py` commits and returns the instance. No redaction happens here, so the raw payload is stored unmasked at this point.
2. **Background pickup.**
   - `process_organization_signals` (`signal/flows.py:406`) fetches unprocessed instance IDs. It passes them in batches to `process_signal_batch` (`flows.py:385`), which calls `signal_instance_create_flow` for each one.
   - `dispatch/cli.py:1004`, in `process_signals`, also calls `signal_instance_create_flow`.
   - I did not trace what schedules `process_organization_signals`.
3. **`signal_instance_create_flow`** (`flows.py:46`), in order:
   - It loads the instance.
   - **It redacts:** `signal_instance.raw = redact_raw(signal_instance.raw)` at `flows.py:60`. The comment there says the masking is done "before entities are extracted from the payload".
   - It collects entity types and runs `entity_service.find_entities`, then commits.
   - It calls `signal_service.filter_signal`. If a filter action applies (for example dedup or snooze), it logs, updates the signal message if needed, and returns. No new case is opened.
   - Otherwise, canary signals, or signals with `create_case` off, are stored and returned.
   - The rest of the flow builds the case from case type, priority, oncall assignee and conversation target.

**The redaction function**

`redact_raw` in `src/dispatch/signal/redaction.py` replaces the value of every matching key with `"[REDACTED]"`. Keys match case-insensitively, at any depth, inside dicts and lists. It returns a copy.

The default key list is `SIGNAL_REDACTED_RAW_FIELDS` in `dispatch/config.py:98`, overridable through the environment variable of the same name. The default is `password,secret,api_key,session_token,authorization`.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no