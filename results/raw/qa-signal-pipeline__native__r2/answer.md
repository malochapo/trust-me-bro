**Flow**

1. `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `signal/views.py`.
   - It resolves the project and the signal definition, using external id, variant, then the default definition. It returns 404 if none exists.
   - It then calls `signal_service.create_instance` and commits. The raw payload is stored unredacted. A duplicate id returns 409.
   - `background_tasks` is a parameter of the handler, but the handler never uses it. The request returns right after the commit.
   - The instance has `filter_action` and `case_id` unset at this point. `signal/service.py` has no redaction code.

2. Later, a separate worker picks the instance up.
   - The `signals consume` loop in `cli.py` (around line 1000) queries instances with `filter_action IS NULL` and `case_id IS NULL`, oldest first.
   - It calls `signal_flows.signal_instance_create_flow` for each one, committing per instance. `process_signal_batch` in `signal/flows.py` does the same thing in batches.

3. `signal_instance_create_flow` in `signal/flows.py` does the following, in order:
   - It loads the instance.
   - It redacts the payload with `signal_instance.raw = redact_raw(signal_instance.raw)`, whose comment reads "mask sensitive values before entities are extracted".
   - It gathers the entity types and runs `entity_service.find_entities`.
   - It calls `signal_service.filter_signal`. If a filter matched (snooze or deduplicate), it returns and no new case is opened.
   - Otherwise it returns early for canary signals or when `create_case` is false.
   - Otherwise it creates a case.

**Redaction**

- `redact_raw` is in `signal/redaction.py`. It returns a copy of the payload with each matching key's value replaced by `"[REDACTED]"`. Keys match case-insensitively, at any depth, inside dicts and lists.
- The default key list is `SIGNAL_REDACTED_RAW_FIELDS` in `config.py`. The `SIGNAL_REDACTED_RAW_FIELDS` environment variable can override it, and its default is `password,secret,api_key,session_token,authorization`.
- Redaction runs before entity extraction and before filtering, so entities and filters only see masked values.
- It does not run during the API request. It runs in the asynchronous consumer, so the unredacted payload is in the database until that worker processes the instance.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no