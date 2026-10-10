The API request does not redact anything. Redaction happens later, in a separate signal-processing loop, before entity extraction.

**API request.** `POST /instances` is `create_signal_instance` in `signal/views.py:72`.
- It resolves the project, then finds the signal definition by external id or variant. If none matches it falls back to the default definition, or returns 404.
- It calls `signal_service.create_instance` (`signal/service.py:650`) and commits.
- `create_instance` copies `raw` (dropping `oncall_service` if set), round-trips it through JSON, builds the `SignalInstance` and sets the case priority, case type and oncall service. It also validates the UUID, which returns 400 if the id is invalid.
- The view returns on a duplicate id with 409.
- The view does not call `signal_instance_create_flow`, and the `background_tasks` argument is unused. The stored `raw` is therefore unredacted at this point.

**Asynchronous processing.**
- `main_processing_loop` runs `process_organization_signals`, which runs `process_signal_batch` (`signal/flows.py:385`).
- The batch calls `signal_instance_create_flow` (`signal/flows.py:46`) for each instance. `cli.py:1004` also calls it, from a CLI path.
- The flow first fetches the instance, then redacts it: `signal_instance.raw = redact_raw(signal_instance.raw)` (`signal/flows.py:60`).
- Next it gathers entity types and runs `entity_service.find_entities`.
- Then `signal_service.filter_signal` runs. If a filter (snooze, dedupe and so on) matches, the flow logs it, updates the signal message if there is a case, and returns. That is the "filtered out" outcome.
- Otherwise a canary signal, or one with `create_case` off, just returns.
- Otherwise the flow continues to case creation.

**Redaction function.** `redact_raw` in `signal/redaction.py` returns a copy of `raw` with each matching key's value replaced by `[REDACTED]`.
- Keys match case-insensitively, at any depth, inside dicts and lists.
- The key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which can be overridden by an environment variable of the same name. The default is `password,secret,api_key,session_token,authorization`.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password, secret, api_key, session_token, authorization
BEFORE_ENTITY_EXTRACTION: yes
DURING_API_REQUEST: no