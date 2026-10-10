Redaction does not happen while the API request is handled. It happens later, in the signal consumer's flow, just before entities are extracted.

**Trace**
1. `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `signal/views.py:72`.
   - It resolves the project.
   - It resolves the signal definition by external id or variant, falling back to the default definition. It returns 404 if none exists.
   - It calls `signal_service.create_instance` (`signal/service.py` around line 660) and commits.
   - `create_instance` stores `raw` as given. It only drops `oncall_service` and round-trips the payload through JSON. It does no redaction.
   - A duplicate id returns 409.
   - The response returns the instance. `BackgroundTasks` is accepted as a parameter but not used for this.
2. The consumer picks the instance up later.
   - `consume_signals` in `cli.py:880` runs a loop. `process_organization_signals` (`signal/flows.py:406`) calls `process_signal_batch`, which calls `signal_instance_create_flow` for each id.
3. `signal_instance_create_flow` (`signal/flows.py:46`) does the following in order:
   - It loads the instance.
   - It sets `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60). This is before entity extraction.
   - It gathers the entity types and calls `entity_service.find_entities`.
   - It calls `signal_service.filter_signal`. If a filter action applies (snooze or deduplicate), it returns, updating the Slack signal message if needed.
   - Canary instances, and signals with `create_case` off, are stored and returned.
   - Otherwise it carries on to case creation.

**Redaction details**
- `redact_raw` in `signal/redaction.py` returns a copy of the payload. It replaces the value of any matching key with `"[REDACTED]"`.
- Keys match case-insensitively, at any depth, inside dicts and lists.
- The key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`. It is configurable through an environment variable and defaults to `password,secret,api_key,session_token,authorization`.

The unredacted payload is stored in the database from the API call until the consumer runs the flow.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no