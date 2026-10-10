The API request handler does not redact anything. It stores the raw payload as received and returns. Redaction happens later, in a background worker, before entities are extracted.

**Trace**

1. `POST /instances` is handled by `create_signal_instance` in `signal/views.py:70`.
   - It resolves the project and the signal definition. That is looked up by `externalId` or `variant`, then falls back to the default definition, and the request returns 404 if neither exists.
   - It calls `signal_service.create_instance`, which builds a `SignalInstance`. `raw` is only copied and JSON round-tripped (`signal/service.py:650`). The instance is committed and returned, with a 409 on a duplicate id.
   - Nothing in this path calls the redaction function.
2. The view does not start the processing flow. `signal_instance_create_flow` is called from `process_batch` in `signal/flows.py:394` and from the CLI at `cli.py:1004`. `process_batch` is run by the signal-consumption loop in `signal/flows.py` (`process_organization_signals`, refreshed every `LOOP_DELAY`=60s). I did not trace the loop's scheduling or its query for unprocessed instances beyond what is quoted above. The flow therefore runs asynchronously, after the API response has been sent.
3. `signal_instance_create_flow` (`signal/flows.py:46`) does the following, in order:
   - It loads the instance.
   - It redacts the payload with `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60).
   - It gathers entity types and runs `entity_service.find_entities`.
   - It calls `signal_service.filter_signal`. If a filter applied (dedupe or snooze), it logs and returns, updating the Slack signal message when the instance is attached to an existing case.
   - It returns early for canary signals or signals with `create_case` false.
   - Otherwise it goes on to create the case.

**Redaction function**

`redact_raw` in `dispatch/signal/redaction.py` returns a copy of the payload with matching values replaced by `[REDACTED]`. Matching is case-insensitive, at any depth, and inside dicts and lists.

The default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`. It can be overridden through that environment variable.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no