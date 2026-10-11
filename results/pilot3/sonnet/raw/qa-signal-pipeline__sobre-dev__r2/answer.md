The redaction does not happen while the API request is handled. It happens later, in an asynchronous processing flow.

**Trace**

1. **API handler.** `create_signal_instance` in `src/dispatch/signal/views.py:72` handles `POST /instances`.
   - It resolves the project.
   - It finds the signal definition by external id or variant, falling back to the default definition. It returns 404 if there is none.
   - It calls `signal_service.create_instance` and commits. A duplicate id returns 409.
   - It returns the instance. It does not call the flow and it does not redact.
2. **Storage.** `signal_service.create_instance` (`signal/service.py`) copies `raw`, drops `oncall_service`, and round-trips it through JSON. It stores the payload unredacted. At this point `filter_action` and `case_id` are both null.
3. **Background pickup.** A separate worker, the signal consumer loop in `cli.py` (~line 985), runs outside the request. It queries instances where `filter_action IS NULL` and `case_id IS NULL`, up to 500 at a time and oldest first. For each one it calls `signal_flows.signal_instance_create_flow`. `process_signal_batch` in `signal/flows.py` also calls it.
4. **Flow.** `signal_instance_create_flow` (`signal/flows.py:46`) runs these steps in order:
   - **Redaction.** `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60), under the comment "mask sensitive values before entities are extracted".
   - **Entity extraction.** It runs `entity_service.find_entities` using the `all`-scope entity types plus the signal's own entity types.
   - **Filtering.** `signal_service.filter_signal` runs next. If a filter acts (snooze, deduplicate and so on), the flow returns, and it may update the Slack signal message.
   - **Early returns.** Canary signals, and signals with `create_case` off, are stored and the flow returns.
   - **Case creation.** Otherwise the flow goes on to create a case.

**Redaction details**

- The function is `redact_raw` in `src/dispatch/signal/redaction.py`.
- It returns a copy of the payload. Any key named in the field list has its value replaced with `[REDACTED]`.
- Keys match case-insensitively, at any depth, inside dicts and lists.
- The key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py`. It can be overridden with an env var of the same name.
- The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.

Until the worker processes the instance, the raw payload sits in the database unredacted. The API response from the POST also returns the unredacted instance.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no