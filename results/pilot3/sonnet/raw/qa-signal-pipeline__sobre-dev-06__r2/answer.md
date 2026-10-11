The redaction is not done while the API request is handled. It runs later, in the signal-processing flow, before entities are extracted.

**1. API request.** `create_signal_instance` in `signal/views.py:70` handles `POST /instances`.
- It resolves the project and the signal definition, either from the raw `externalId` or `variant` or from the project default. It returns 404 if neither exists.
- It then calls `signal_service.create_instance` (`signal/service.py`) and commits.
- `create_instance` copies `raw`, drops `oncall_service` and round-trips it through JSON. **The raw payload is stored unredacted.** A duplicate id returns 409.
- The view returns the instance without calling `signal_instance_create_flow`, even though it takes a `background_tasks` parameter.

**2. Background processing.**
- `process_organization_signals` and `process_signal_batch` in `signal/flows.py` (around line 380) pick up unprocessed instances. This runs outside the request, from a periodic consumer. `cli.py:1004` also calls the flow.
- For each instance they call `signal_instance_create_flow` (`signal/flows.py:46`).

**3. Redaction (first step of the flow).**
- Line 60 is `signal_instance.raw = redact_raw(signal_instance.raw)`, with the comment "mask sensitive values before entities are extracted".
- `redact_raw` is in `signal/redaction.py`. It returns a copy of the payload in which the value of every matching key is replaced with `"[REDACTED]"`.
- Matching ignores case and applies at any depth, inside dicts and lists.
- The default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which can be overridden by an environment variable of the same name. The default is `password,secret,api_key,session_token,authorization`.

**4. Entity extraction and filtering.**
- The flow gathers the entity types, calls `entity_service.find_entities` and commits.
- It then calls `signal_service.filter_signal`. If a filter acted (snooze or deduplicate), it logs, updates the signal message if a case exists, and returns.
- Otherwise it returns early for canary signals and for signals where `create_case` is false.
- Only after those checks does it go on to create a case.

Between the API commit and the background flow, the unredacted `raw` sits in the database.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no