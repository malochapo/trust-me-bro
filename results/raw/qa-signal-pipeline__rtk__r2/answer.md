The API handler doesn't redact anything. The instance is stored as received, and a background consumer redacts it later.

**What happens to the instance**
1. `create_signal_instance` in `signal/views.py:70` handles `POST /instances`.
   - It resolves the project.
   - It finds the signal definition, trying `externalId` or `variant` from the raw payload first and falling back to the project default. It returns 404 if none exists.
   - It calls `signal_service.create_instance` and commits. A duplicate id returns 409.
   - It returns the instance. No flow is called here, and `background_tasks` is never used.
   - At this point `raw` is still unredacted.
2. The instance is left with `filter_action` and `case_id` both unset. A separate worker finds it there.
   - That worker is `process_organization_signals` in `signal/flows.py`. The `cli.py` signal consumer (around line 1004) does the same thing.
   - Both query for instances with `filter_action IS NULL` and `case_id IS NULL`, oldest first.
   - For each one they call `signal_flows.signal_instance_create_flow` and then commit.
3. `signal_instance_create_flow` in `signal/flows.py:46` runs these steps in order:
   - It first reloads the instance and sets `signal_instance.raw = redact_raw(signal_instance.raw)` (`flows.py:60`).
   - It then collects the entity types for the signal plus the `all`-scoped ones. If there are any, it runs `entity_service.find_entities` and commits.
   - Next is `signal_service.filter_signal`. If a filter action applies (snooze, deduplicate, and so on), it returns early. It also refreshes the signal message when the instance was deduplicated into an existing case.
   - After that, canary signals and signals with `create_case` off are stored and returned.
   - Otherwise the flow goes on to create a case.

**Redaction**
- `redact_raw` in `signal/redaction.py` returns a copy of `raw` with each matching key's value replaced by `[REDACTED]`.
- Keys match case-insensitively, at any depth, inside dicts and lists.
- The key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`. It defaults to `password,secret,api_key,session_token,authorization` and can be overridden with an environment variable.
- It runs before entity extraction, so extracted entities never see the sensitive values.
- It does not run during the API request. Until the worker picks the instance up, the unredacted `raw` is committed to the database.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no