Redaction does not happen while the API request is handled. It happens later, in the background signal-processing loop.

**1. API request (`signal/views.py:72`, `create_signal_instance`)**
- It resolves the project.
- It finds the signal definition by `externalId` or `variant` in the raw payload, falls back to the project's default definition, and returns 404 if neither exists.
- It calls `signal_service.create_instance(...)` and commits. A duplicate id returns 409.
- It returns the instance.
- There is no call to the flow or to any redaction here, and `signal/service.py`'s `create_instance` doesn't redact either. The `BackgroundTasks` parameter is accepted but not used. At this point the raw payload is stored unredacted, with `filter_action` and `case_id` both empty.

**2. Background worker (`cli.py`, around line 950–1010)**
- A loop runs per organization schema.
- It selects up to 500 `SignalInstance` rows where `filter_action` and `case_id` are both NULL, oldest first.
- It calls `signal_flows.signal_instance_create_flow(...)` on each one, committing after each.

**3. `signal_instance_create_flow` (`signal/flows.py:46`)**
- The first step after loading the instance is `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60).
- Entity extraction (`entity_service.find_entities`) comes after that, so entities are extracted from the redacted payload.
- `signal_service.filter_signal` runs next. If a filter matches, the instance is deduplicated or snoozed, any existing signal message is updated, and the flow returns.
- Otherwise a canary instance is stored and the flow returns. If the signal's `create_case` is false, it also returns. In all other cases the flow continues and creates a case.

**4. The redaction function (`signal/redaction.py`, `redact_raw`)**
- It returns a copy of the payload in which the value of every matching key is replaced with `"[REDACTED]"`.
- Matching is case-insensitive and applies at any depth, inside dicts and lists.
- The key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`. It can be overridden with an environment variable of the same name.
- The default keys are `password,secret,api_key,session_token,authorization`.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no