A signal instance posted to the API is stored unredacted during the request. A separate background consumer redacts it later, before entity extraction.

**1. API request.** The handler is `create_signal_instance` in `signal/views.py:72`.
- It resolves the project.
- It looks up the signal definition by `externalId` or `variant` in the raw payload, then falls back to the project's default definition. It returns a 404 if neither exists.
- It calls `signal_service.create_instance`, which copies the raw payload and drops `oncall_service`. It then round-trips the copy through JSON and persists it with `db_session.commit()`.
- It returns the instance. A duplicate id gives a 409.
- Nothing in this path redacts the payload. The `background_tasks` argument is accepted but never used, and the handler does not call the flow.
- The new instance has `filter_action` and `case_id` both unset, which marks it as unprocessed.

**2. Background processing.** The unprocessed instances are picked up outside the request.
- The CLI signal consumer in `cli.py` (around line 1004) selects up to 500 instances where `filter_action IS NULL` and `case_id IS NULL`, oldest first. It calls `signal_flows.signal_instance_create_flow` on each one and commits.
- `process_signal_batch` in `signal/flows.py` (around line 394) does the same for a batch of ids.

**3. `signal_instance_create_flow` (`signal/flows.py`).**
1. It loads the instance.
2. It redacts the payload with `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60). A comment there says this masks sensitive values before entities are extracted.
3. It gathers the entity types: the signal's own types plus those with scope `all`.
4. It runs `entity_service.find_entities`, which now sees the redacted payload.
5. It calls `signal_service.filter_signal`. If a filter acted (snooze, deduplicate and so on), it logs the filter, updates the Slack signal message if needed, and returns. No case is opened.
6. Otherwise it returns early for canary signals, or when the signal has `create_case` off.
7. Otherwise it continues on to open a case.

**4. Redaction.** `dispatch.signal.redaction.redact_raw` (in `signal/redaction.py`) returns a copy of the payload.
- It replaces the value of any matching key with `"[REDACTED]"`.
- Keys match case-insensitively, at any depth, inside dicts and lists.
- The key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py`. It is configurable through the environment variable of the same name and defaults to `password,secret,api_key,session_token,authorization`.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no