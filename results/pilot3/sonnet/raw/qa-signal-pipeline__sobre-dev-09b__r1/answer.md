The raw payload is redacted in a background consumer, not while the API request is handled. The request stores the raw payload unredacted.

**1. API request (`signal/views.py`, `create_signal_instance`)**
- The endpoint resolves the project and the signal definition. It looks the definition up by `externalId` or `variant` in the payload, and falls back to the project's default signal. If it finds none, it returns 404.
- It then calls `signal_service.create_instance`, which builds the `SignalInstance` with `raw=json.loads(json.dumps(raw))`. The `raw` field holds the full payload with no redaction.
- It commits and returns the instance. A duplicate id returns 409, and a non-UUID id returns 400.
- `background_tasks` is a parameter on the view but is never used. The view does not call `signal_instance_create_flow`.

**2. Background processing (`cli.py`, around line 1004)**
- A signal consumer loop selects instances where `filter_action IS NULL` and `case_id IS NULL`, oldest first, up to 500 per organization.
- It calls `signal_flows.signal_instance_create_flow` on each one. `signal/flows.py:process_signal_batch` does the same.

**3. `signal_instance_create_flow` (`signal/flows.py:46`)**
- Its first step is `signal_instance.raw = redact_raw(signal_instance.raw)`, at line 60.
- The comment there says it masks sensitive values before entities are extracted.
- Entity extraction follows: it gathers the signal's entity types plus the `all`-scoped ones, then calls `entity_service.find_entities`.
- `signal_service.filter_signal` then runs. If a filter matched (snooze or deduplicate), it returns early, and it may update the case's signal message.
- If the instance is a canary, or the signal has `create_case` off, it stores the instance and returns without opening a case.
- Otherwise the flow resolves the case type, priority, oncall service and conversation target, and creates the case.

**Redaction function (`signal/redaction.py`)**
- `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` returns a copy of `raw` in which the value of every matching key is replaced with `"[REDACTED]"`.
- Keys match case-insensitively, at any depth, inside dicts and lists.
- The default keys come from `config.py` (`SIGNAL_REDACTED_RAW_FIELDS`, overridable by an environment variable of the same name): `password,secret,api_key,session_token,authorization`.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no