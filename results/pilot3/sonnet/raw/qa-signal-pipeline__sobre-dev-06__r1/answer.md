Redaction does not happen while the API request is handled. It happens later, in the background signal-consumer loop, just before entity extraction.

**Flow**
1. `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `signal/views.py:72`.
   - It resolves the project and the signal definition. It looks one up by external id or variant, falls back to the default, and returns 404 if none exists.
   - It calls `signal_service.create_instance` and commits. A duplicate id returns 409.
   - It returns the instance without redacting anything. `raw` is stored as received. The `background_tasks` argument is never used.
2. The instance is stored with `filter_action` and `case_id` both unset. The consumer in `cli.py` (around line 990) selects instances in that state, oldest first, up to 500 at a time. It calls `signal_flows.signal_instance_create_flow` for each one and commits after each.
3. `signal_instance_create_flow` (`signal/flows.py:46`) runs these steps in order:
   - **Redaction:** `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60).
   - **Entity extraction:** it gathers the signal's entity types plus the global ones, then calls `entity_service.find_entities`.
   - **Filtering:** `signal_service.filter_signal` runs. If a filter acts, for example a snooze or deduplication, the flow returns there. A deduplicated instance can also update the existing case's signal message.
   - **Early returns:** canary instances, and signals with `create_case` off, return without opening a case.
   - **Case creation:** otherwise the flow continues, applying the case type, priority and so on, and opens a case.

**Redaction details**
- `redact_raw` is in `signal/redaction.py`.
- It replaces matching values with `"[REDACTED]"`.
- Keys match case-insensitively, at any depth, inside dicts and lists.
- The key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`. The environment variable of the same name can override it. The default is `password,secret,api_key,session_token,authorization`.
- Because redaction runs before entity extraction, extracted entities and any case created from the instance never see the original values. The raw values do sit in the database between the API commit and the consumer's pass.

I read the code but did not run it.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no