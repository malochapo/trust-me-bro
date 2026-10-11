Redaction doesn't happen while the API request is handled. It happens later, in the background signal-processing flow.

**1. API request.** `create_signal_instance` is in `signal/views.py:70`. It does the following:
- It resolves the project.
- It finds the signal definition by `externalId`/`variant`, falling back to the default definition. If none exists, it returns a 404.
- It calls `signal_service.create_instance` and commits. A duplicate id returns a 409.
- It returns the instance.

The view never calls the flow and never redacts. The `raw` payload is stored as received, and the view even reads `raw["externalId"]` and `raw["variant"]` from it unredacted.

**2. Background processing.** `process_organization_signals` in `signal/flows.py` fetches unprocessed instance ids. It passes them through `process_signal_batch` to `signal_instance_create_flow`. A scheduler loop does this, and `cli.py:1004` also calls the flow.

**3. Inside `signal_instance_create_flow`, in order:**
- **Redaction:** `signal_instance.raw = redact_raw(signal_instance.raw)`, with the comment "mask sensitive values before entities are extracted".
- **Entity extraction:** `entity_service.find_entities`, using the signal's entity types plus the global ones.
- **Filtering:** `signal_service.filter_signal`. If a filter acts (snooze, deduplicate and so on), the flow returns early. It may update the signal message on an existing case.
- **Canary and `create_case` checks:** canary instances, and signals with `create_case` off, are stored and returned without a case.
- **Case creation:** otherwise the flow goes on to create a case.

**The redaction function.** `redact_raw` is in `signal/redaction.py`. It returns a copy of the payload. Any value whose key matches a configured name is replaced with `"[REDACTED]"`. Matching is case-insensitive and applies at any depth, inside dicts and lists.

**Default keys.** `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98` supplies them: `password,secret,api_key,session_token,authorization`. The `SIGNAL_REDACTED_RAW_FIELDS` environment variable can override them.

Until the background flow runs, the unredacted payload sits in the database.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no