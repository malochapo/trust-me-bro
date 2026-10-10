The raw payload is redacted by a background consumer, not while the API request is being handled. The request handler stores the payload as received.

**Flow**
1. `POST /api/v1/{organization}/signals/instances` runs `create_signal_instance` in `signal/views.py:70`.
   - It resolves the project.
   - It finds the signal definition by external id or variant, then falls back to the default definition. If neither exists it returns a 404.
   - It calls `signal_service.create_instance` (`signal/service.py:650`) and commits.
   - A duplicate id returns a 409.
   - It returns the instance. The `signal_instance_create_flow` function isn't called from the view, and the view doesn't use its `background_tasks` argument.
   - I did not read the rest of `create_instance`. Redaction isn't called anywhere in the request path.
2. The instance is saved with `filter_action` and `case_id` both unset, so it counts as unprocessed. A separate process picks it up:
   - `process_organization_signals` and `process_signal_batch` in `signal/flows.py:385` and following do this.
   - The loop at `cli.py:~985–1010` also does this. It selects instances where both fields are null, ordered by `created_at`, up to 500.
   - Both call `signal_flows.signal_instance_create_flow` for each instance.
3. `signal_instance_create_flow` (`signal/flows.py:46`) does the following, in order:
   - It loads the instance.
   - **It redacts the payload:** `signal_instance.raw = redact_raw(signal_instance.raw)` at line 60.
   - It extracts entities with `entity_service.find_entities`, using the entity types of the signal definition plus the scope-`all` types.
   - It runs `signal_service.filter_signal`. If a filter acts (for example dedup or snooze), it logs this, updates the Slack signal message if needed, and returns. No case is opened.
   - It returns without a case for canary signals, and for signals where `create_case` is false.
   - Otherwise it resolves case type, priority, severity, oncall assignee and conversation target, then creates a `CaseCreate` through `case_service.create`. It links the case to the instance and continues into the case creation flow.

**The redaction function** is `redact_raw` in `signal/redaction.py`.
- It returns a copy of the payload with the value of each matching key replaced by `"[REDACTED]"`.
- Keys match case-insensitively, at any depth, inside dicts and lists.
- The key list comes from the `SIGNAL_REDACTED_RAW_FIELDS` setting in `config.py:98`. It is configurable through an environment variable of the same name.
- The defaults are `password,secret,api_key,session_token,authorization`.

The only difference from the stored payload is that `raw` is overwritten with the redacted copy in step 3. Until the background job runs, the unredacted payload sits in the database.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no