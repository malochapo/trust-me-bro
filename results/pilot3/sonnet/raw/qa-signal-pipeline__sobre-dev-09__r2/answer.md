Redaction happens in the background signal consumer, not in the API request, and it runs before entity extraction.

**Request handling**
- `create_signal_instance` in `signal/views.py:72` handles `POST /instances`. It resolves the project and the signal definition, using `raw["externalId"]` or `raw["variant"]`, with the default definition as fallback.
- It then calls `signal_service.create_instance` and commits. A duplicate id returns 409.
- It returns the instance without calling any flow. `background_tasks` is accepted as a parameter but never used.
- The instance is therefore stored with its raw payload unredacted at this point, and the API response is built from that stored instance.

**Background processing**
- The signal consumer in `cli.py` (around line 975) loops over the organizations. In each one it selects up to 500 instances that have no `filter_action` and no `case_id`, oldest first. It calls `signal_flows.signal_instance_create_flow` for each and commits after each one.
- `process_signal_batch` in `signal/flows.py` (around line 390) also calls the flow.

**`signal_instance_create_flow` (`signal/flows.py:46`)**
1. It loads the instance and then runs `signal_instance.raw = redact_raw(signal_instance.raw)`. The comment there says this masks sensitive values before entities are extracted.
2. It gathers the entity types and calls `entity_service.find_entities`, which reads the already-redacted `raw`.
3. It calls `signal_service.filter_signal`. If a filter matches, the instance is snoozed or deduplicated and the flow returns. A deduplicated instance is attached to an existing case, and its Slack signal message is updated if needed.
4. Canary signals are stored and the flow returns. The same happens when `create_case` is false.
5. Otherwise it resolves the case type, priority, oncall and conversation target and opens a case.

**The redaction function**
- `redact_raw` is in `signal/redaction.py`. It returns a copy of the payload with the value of every listed key replaced by `"[REDACTED]"`.
- Matching is case-insensitive and applies at any depth, inside dicts and lists.
- The default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which can be overridden by an environment variable of the same name. The default is `password,secret,api_key,session_token,authorization`.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no