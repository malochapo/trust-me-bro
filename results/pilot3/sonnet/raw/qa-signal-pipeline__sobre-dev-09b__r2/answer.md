Redaction does not happen while the API request is being handled. It happens later, in a separate processing step.

**Trace**

1. **API request.** `POST /instances` is handled by `create_signal_instance` in `signal/views.py:72`.
   - It resolves the project and the signal definition (by externalId or variant, falling back to the project default). It returns 404 if there is no definition.
   - It calls `signal_service.create_instance` (`signal/service.py:650`) and commits.
   - `create_instance` only drops `oncall_service` from the raw payload and round-trips it through JSON. It does no redaction.
   - The handler takes a `BackgroundTasks` argument but never uses it. It returns the stored instance, so the raw payload is saved unredacted at this point.
2. **Pickup.** The instance is not processed in the request. A separate worker loop in `signal/flows.py` finds unprocessed instances with `get_unprocessed_signal_instance_ids`. It then calls `process_signal_batch` (`signal/flows.py:386`), which calls `signal_instance_create_flow` for each one. `cli.py:1004` also calls the flow.
3. **Flow.** `signal_instance_create_flow` (`signal/flows.py:47`) does these steps in order:
   - Redaction: `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60), under the comment "mask sensitive values before entities are extracted".
   - Entity extraction: it collects the entity types and calls `entity_service.find_entities`.
   - Filtering: `signal_service.filter_signal` applies the snooze and dedup filters. If one matches, the flow returns early without opening a case. It may update the Slack signal message first.
   - Other early returns: canary signals, and signals with `create_case` off, are stored and returned.
   - Otherwise it resolves case type, priority, oncall and conversation target, and creates the case.

**Redaction function**

`dispatch.signal.redaction.redact_raw` is defined in `signal/redaction.py`.
- It returns a copy of the payload in which each matching key's value is replaced with `"[REDACTED]"`.
- Keys match case-insensitively, at any depth, inside dicts and lists.
- The key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`. It can be overridden with an environment variable of the same name.
- The default is `password,secret,api_key,session_token,authorization`.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no