Redaction does not happen while the API request is being handled. It happens later, in a separate signal-consumer process.

**Trace**

1. `POST /api/v1/{organization}/signals/instances` runs `create_signal_instance` in `signal/views.py:72`.
   - It resolves the project.
   - It finds the signal definition by external id or variant, falls back to the default definition, and returns 404 if neither exists.
   - It calls `signal_service.create_instance` and commits. A duplicate id returns 409.
   - It returns the instance with the **raw payload still unredacted**. It never calls `signal_instance_create_flow`, and `background_tasks` is a parameter but is not used.
2. The new instance is stored with no `filter_action` and no `case_id`. The signal consumer loop in `cli.py` (around line 985) polls for such instances, up to 500 at a time, oldest first. It calls `signal_flows.signal_instance_create_flow` for each one and commits after each. `process_signal_batch` in `signal/flows.py` (around line 385) does the same for a list of ids.
3. `signal_instance_create_flow` (`signal/flows.py:46`) does the following in order:
   - It loads the instance.
   - **It runs `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60).** This is the first processing step, with the comment "mask sensitive values before entities are extracted".
   - It gathers entity types and runs `entity_service.find_entities`.
   - It calls `signal_service.filter_signal`. If a filter acts (snooze or deduplicate), it logs, updates the signal message if needed, and returns.
   - Otherwise it returns early if the instance is a canary or if `create_case` is false.
   - Otherwise it goes on to open a case.

**Redaction details**

- `redact_raw` is in `signal/redaction.py`. It returns a copy of the payload. Keys match case-insensitively at any depth, inside dicts and lists. Matching values are replaced with `[REDACTED]`.
- The key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`. It can be overridden by an environment variable of the same name. The default is `password,secret,api_key,session_token,authorization`.
- Because redaction happens before entity extraction, entities are extracted from the masked payload.
- The unredacted payload is committed to the database at API time, and it stays there until the consumer processes the instance.
- `redact_raw` only changes `signal_instance.raw`. The flow commits only inside the entity branch (`db_session.commit()` after `find_entities`). In the other cases the mask relies on the caller's commit.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no