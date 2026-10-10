The API handler only stores the signal instance. A background consumer processes it later, and redaction happens in that consumer's flow.

**Trace**
1. `POST /instances` is handled by `create_signal_instance` in `signal/views.py:70`. It resolves the project and the signal definition, either by the payload's `externalId` or `variant`, or by falling back to the default definition. It returns 404 if neither is found.
2. It then calls `signal_service.create_instance` (`signal/service.py:650`). That function copies `raw` with a JSON round-trip, with no redaction. It sets the case priority, case type and oncall service, and adds the row to the session. The view then commits. A duplicate id returns 409.
3. The view never calls the flow, even though it takes `background_tasks`. It returns the stored instance with the raw payload intact.
4. A separate loop picks up unprocessed instances. `process_organization_signals` and `process_signal_batch` (`signal/flows.py:~380`) call `signal_instance_create_flow`. The CLI at `cli.py:1004` also calls it.
5. The first thing the flow does is `signal_instance.raw = redact_raw(signal_instance.raw)` (`signal/flows.py:60`). After that it does the following:
   - It extracts entities.
   - It runs `signal_service.filter_signal`. If a filter acts (snooze, deduplicate and so on), the flow returns there. If a deduplicated instance already has a case, it updates that case's signal message.
   - It returns early for canary signals and for signals that don't have `create_case` set.
   - Otherwise it creates the case.

**Redaction**
- `redact_raw` in `signal/redaction.py` returns a copy of the payload in which the value of any matching key becomes `[REDACTED]`. Keys are matched case-insensitively, at any depth, inside dicts and lists.
- The default keys come from the `SIGNAL_REDACTED_RAW_FIELDS` setting in `config.py:98`. It can be overridden with an environment variable of the same name.
- Redaction runs before entity extraction and before filtering. It does not run during the API request. Until the background flow processes the instance, the committed row holds the unredacted payload.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no