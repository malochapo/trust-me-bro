**Trace**

1. **API request.** `POST /instances` is handled by `create_signal_instance` in `signal/views.py:70`. It does these steps:
   - It resolves the project and the signal definition, either by `externalId`/`variant` from the raw payload or by falling back to the default definition.
   - It returns a 404 if no definition exists.
   - It calls `signal_service.create_instance(...)` and commits, returning a 409 on `IntegrityError`.
   - It then returns the instance.

   The view takes a `BackgroundTasks` parameter but never uses it. It doesn't call `signal_instance_create_flow` and doesn't redact anything. A grep for `redact` across `signal/` finds it only in `flows.py` and `redaction.py`, so `create_instance` doesn't redact either. At this point the unredacted `raw` is stored in the database.

2. **Background processing.** A periodic job, `process_organization_signals`, reads the ids from `get_unprocessed_signal_instance_ids`. It passes them to `process_signal_batch`, which calls `signal_flows.signal_instance_create_flow` for each id and commits after each one. This is in `signal/flows.py:~380-400`. `cli.py:1004` also calls the flow.

3. **`signal_instance_create_flow`** (`signal/flows.py:46`) runs these steps in order:
   - It loads the instance.
   - **It redacts:** `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60).
   - It finds entities with `entity_service.find_entities`, using the signal's entity types plus the "all" scope types.
   - `signal_service.filter_signal` runs. If a filter matches, the flow returns. A deduplicated instance can update the existing case's signal message.
   - Canary signals, and signals with `create_case` off, are stored and the flow returns.
   - Otherwise it resolves case type, priority, oncall and conversation target, and goes on to create the case.

**Redaction function:** `redact_raw` in `signal/redaction.py`.
- It returns a copy of the payload in which any key named in the field list has its value replaced with `"[REDACTED]"`.
- Matching is case-insensitive, works at any depth, and descends into dicts and lists.
- The default fields come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`. You can override that setting with an environment variable of the same name.
- The default keys are `password`, `secret`, `api_key`, `session_token` and `authorization`.

**Timing:** redaction happens before entity extraction and before filtering. It does not happen during the API request. It happens later, when the background job processes the instance, so the raw payload is stored unredacted in the meantime.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no