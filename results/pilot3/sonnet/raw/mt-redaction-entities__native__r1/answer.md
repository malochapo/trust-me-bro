## Recap

**Flow of a signal instance**
- `POST /api/v1/{organization}/signals/instances` (`signal/views.py`) picks the signal definition and calls `signal_service.create_instance`. It then commits the instance to the database with `raw` exactly as received.
- A background consumer later picks up rows with no `filter_action` and no `case_id`. It runs `signal_instance_create_flow` (`signal/flows.py`).
- The flow masks `raw` first, then extracts entities and applies filters. A filtered instance is either deduplicated into an existing case or dropped. Canary signals and signals with `create_case` off stop without a case. Anything else opens a case.

**Masking**
- `redact_raw` replaces the value of any key on the list with `[REDACTED]`. Matching is case-insensitive, at any depth, inside dicts and lists. It matches key names only.
- The default key list comes from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py`. The environment variable of the same name overrides it.
- The unmasked payload is written to the database. The API commits it before the flow masks it, and the masked copy only replaces it on a later commit. Rows created earlier, or ones whose processing fails and rolls back, can stay unmasked. Moving the `redact_raw` call into `create_instance` would stop this. I haven't made that change.

**Bugs fixed this session**
- Entity extraction kept only the first JSONPath match. The cause was `beb60cc4`, "perf(entity): stop at the first JSONPath match". I reverted that line and `tests/entity` passes.
- Unrelated "Personal access token exposed" instances were grouped into one case. The masked token `[REDACTED]` became an entity with the same value on every instance, and the deduplication filter merged them.
- `find_entities` now searches a redacted copy of the payload and skips any match equal to the mask. I added `test_find_entities_ignores_masked_values`.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4