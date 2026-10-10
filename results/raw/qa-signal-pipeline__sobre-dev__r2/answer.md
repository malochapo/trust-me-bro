The redaction does not happen during the API request. It happens later, in the background signal consumer.

**Trace**

1. `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `signal/views.py:72`.
   - It resolves the project and the signal definition. The definition comes from the request, then from the `externalId` or `variant` in the raw payload, then from the project default. If none is found it returns 404.
   - It calls `signal_service.create_instance` (`signal/service.py:650`) and commits. A duplicate id gives 409.
   - `create_instance` copies `raw`, JSON round-trips it and stores it as is. No redaction happens here. The endpoint returns the stored instance without running any flow.
2. A background loop picks the instance up later.
   - `process_organization_signals` (`signal/flows.py:406`) runs per organization. It fetches unprocessed instance ids through `get_unprocessed_signal_instance_ids`.
   - `process_signal_batch` (`signal/flows.py:385`) calls `signal_instance_create_flow` for each id and commits after each one. `cli.py:1004` also calls the flow.
3. `signal_instance_create_flow` (`signal/flows.py:46`) runs these steps in order:
   - It loads the instance and then sets `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60), before any entity extraction.
   - It collects entity types: those on the signal definition plus those with scope `all`.
   - It calls `entity_service.find_entities` and commits the entities.
   - It calls `signal_service.filter_signal`. If a filter acted (snooze or dedup), it logs, updates the signal message if needed and returns, so no new case is opened.
   - A canary signal, or a signal without `create_case`, is stored and returns.
   - Otherwise the flow goes on to set the case attributes and create the case.

**Redaction**

- The function is `redact_raw` in `dispatch/signal/redaction.py`. It returns a copy of `raw`.
- Keys match case-insensitively, at any depth, inside dicts and lists. The value of a matching key becomes `[REDACTED]`.
- The default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`. You can override them with an environment variable of the same name, comma-separated. The defaults are `password`, `secret`, `api_key`, `session_token` and `authorization`.

One consequence: the unredacted payload is stored in the database from the API request until the background flow processes the instance.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no