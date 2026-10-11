The POST handler does not redact anything. Redaction happens later, in the background signal consumer, before entities are extracted.

**Flow**

1. **API request.** `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `signal/views.py:70`.
   - It resolves the project.
   - It finds the signal definition by `externalId` or `variant` in `raw`, falling back to the project's default definition.
   - It calls `signal_service.create_instance` and commits.
   - It returns a 409 on an `IntegrityError`.
   - The raw payload is stored unmodified at this point, and `background_tasks` is never used.
2. **Consumer.** The `consume_signals` CLI command (`cli.py:~880–1010`) loops over organizations.
   - It selects `SignalInstance` rows where `filter_action IS NULL` and `case_id IS NULL`.
   - It calls `signal_flows.signal_instance_create_flow` for each one, in its own transaction.
   - `process_signal_batch` in `signal/flows.py` does the same thing.
3. **`signal_instance_create_flow`** (`signal/flows.py:46`) runs these steps in order:
   - It calls `signal_instance.raw = redact_raw(signal_instance.raw)` as its first real step.
   - It collects entity types (those on the signal definition plus those with scope `all`) and runs `entity_service.find_entities`.
   - It calls `signal_service.filter_signal`. If a filter matches (snooze or deduplicate), the instance is filtered out and a deduplicated instance may update the existing case's Slack message.
   - It returns early for canary signals or when `create_case` is false.
   - Otherwise it works out the case type, priority, oncall and conversation target, and goes on to create the case.

**Redaction**

- `redact_raw` in `dispatch/signal/redaction.py` is the function.
- It returns a copy of the payload.
- It matches keys case-insensitively, at any depth, inside dicts and lists.
- It replaces each matched value with `"[REDACTED]"`.
- The keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which defaults to `password,secret,api_key,session_token,authorization`. The env var of the same name overrides it.

Sensitive values are therefore in the database between the API request and the consumer's next pass.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no