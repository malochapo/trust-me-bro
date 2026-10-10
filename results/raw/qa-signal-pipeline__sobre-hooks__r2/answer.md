Redaction happens in the signal-processing flow, not during the API request. The request handler only stores the raw payload.

**Trace**
1. `POST /instances` is handled by `create_signal_instance` in `signal/views.py`. It resolves the project and then the signal definition, using the external id or variant and falling back to the default definition. It returns 404 if there is no definition.
2. It calls `signal_service.create_instance` and commits. A duplicate id returns 409. The handler never calls the flow, and `background_tasks` is accepted but unused. The raw payload is stored unredacted at this point.
3. A later consumer picks the instance up. In `signal/flows.py`, `process_signal_batch` runs from `process_organization_signals`, the scheduled worker loop. It calls `signal_instance_create_flow`. `cli.py:1004` also calls that flow.
4. `signal_instance_create_flow` redacts first. It runs `signal_instance.raw = redact_raw(signal_instance.raw)` at `signal/flows.py:60`. Entity extraction comes after that, so entities are extracted from the already-redacted payload.
5. It then loads entity types and runs `entity_service.find_entities`.
6. `signal_service.filter_signal` runs next. If a filter applies (dedupe, snooze and so on), the flow logs, updates the signal message if needed, and returns. No new case is opened in that branch.
7. Canary instances, and signals with `create_case` false, are stored and return early. Otherwise the flow goes on to create the case.

**The redaction function**
- `redact_raw` in `signal/redaction.py` replaces the value of any matching key with `"[REDACTED]"`.
- Keys match case-insensitively, at any depth, inside dicts and lists.
- It returns a copy.
- The key list comes from the `SIGNAL_REDACTED_RAW_FIELDS` setting in `config.py`. It can be overridden with an environment variable and defaults to `password,secret,api_key,session_token,authorization`.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no