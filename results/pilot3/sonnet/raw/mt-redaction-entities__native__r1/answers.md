Yes, the unmasked payload is written to the database. The API commits it before any masking happens. Nothing in this trace was changed.

## Trace

1. **API entry** (`signal/views.py:70`, `create_signal_instance`):
   - It resolves the project and picks the signal definition. It tries external id or variant from `raw` first, then the project default. It returns 404 if neither exists.
   - It calls `signal_service.create_instance(...)` and then `db_session.commit()`. A duplicate id gives a 409.
   - It returns the instance. The `background_tasks` argument is accepted but never used, so the API does not run the case flow.
2. **Persist** (`signal/service.py:650`, `create_instance`):
   - The raw payload is copied and round-tripped through JSON (`json.loads(json.dumps(...))`) and stored as `SignalInstance.raw`.
   - It does no masking.
   - The instance starts with no `filter_action` and no `case_id`, which marks it as unprocessed.
3. **Async pickup:**
   - A consumer picks up unprocessed instances. These are rows with `filter_action IS NULL` and `case_id IS NULL`.
   - There are two consumers: the loop in `cli.py` (~line 975–1004) and `process_signal_batch` in `signal/flows.py:~394`. Both call `signal_flows.signal_instance_create_flow`.
4. **Flow** (`signal/flows.py:46`, `signal_instance_create_flow`):
   - **Masking** happens at line 60: `signal_instance.raw = redact_raw(signal_instance.raw)`.
   - **Entity extraction** comes next, using the entity types of the signal and the `all`-scoped ones. It commits if there are entity types.
   - **Filtering** is `signal_service.filter_signal(...)`. If a filter matched, it logs, may update the Slack signal message for a deduplicated case, and returns. No new case is opened.
   - **Early returns without a case:** canary signals, and signals with `create_case` off.
   - **Case creation:** otherwise it resolves case type, priority, oncall service, conversation target and assignee, then creates the case.

## Masking

- **Where:** `signal/flows.py:60`, inside `signal_instance_create_flow`.
- **Which function:** `redact_raw` in `signal/redaction.py:10`, with a private recursive helper `_redact`.
- **How it works:**
  - It returns a copy of the payload. Any key whose lowercased name is in the list gets the value `"[REDACTED]"`.
  - Matching is case-insensitive, applies at any depth, and descends into dicts and lists.
  - It matches key names only. A secret inside a string value, or under a key not on the list, is not touched.
- **Default keys:** `password`, `secret`, `api_key`, `session_token`, `authorization`. These come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`. The env var of the same name overrides them with a comma-separated list. Matching is exact, so `x-api-key` or `client_secret` would not be masked.

## Is the unmasked payload written to the database?

Yes, for a window of time, and possibly permanently.

- `create_instance` stores the raw payload as received, and the view commits it at `views.py:~120`. The row therefore exists unmasked.
- Masking only runs later in the async flow. Even then it is only an ORM attribute reassignment. It reaches the database when the next commit runs, either the entity commit or the consumer's per-instance commit.
- **Consequences:**
  - Between the API commit and that later commit, secrets sit in plaintext in `signal_instance.raw`. Anyone who reads that table or the `GET /instances` endpoint in that window sees them.
  - The response of the POST itself returns the `SignalInstanceRead`, which likely includes the unmasked `raw`.
  - If the flow fails or is rolled back, the consumer calls `db_session.rollback()`. The row stays unmasked and is retried.
  - Any instance created before this redaction was added is never redacted, because only unprocessed rows go through the flow.
  - DB logs, WAL and backups can retain the original value even after the update.

## Other things I noticed

- The flow redacts before entity extraction, so extracted entities and filters see masked values. Filter and entity rules that depend on the original value of a masked key will not work.
- In `views.py`, `external_id` and `variant` are only defined when `signal_instance_in.signal` is empty. If a signal is supplied and later lookups fail, the log message would raise a `NameError`. Also, `signal_definition` is only set inside that branch.
- `flows.py:~56` uses `"%%s"` in a log format string, which looks like a typo.

If you want a fix, the usual one is to call `redact_raw` in `create_instance`, before the `SignalInstance` is built. That way the unmasked value never reaches the database.

----- next turn -----

Entity extraction now returns every JSONPath match again, and the 11 tests in `tests/entity` pass.

The cause was commit `beb60cc4`, "perf(entity): stop at the first JSONPath match". It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`. That kept only the first match for each entity type. I reverted that line to `jpath.find(signal_instance.raw)` and removed the comment that justified it. I didn't touch the tests.

I only ran `tests/entity`, not the full suite.

----- next turn -----

Unrelated "Personal access token exposed" instances were grouped because the masked token itself became an entity. The fix is in, with a new test. `tests/entity` and `tests/signal` give 44 passed and 1 skipped; I didn't run the rest of the suite.

**Why they grouped:** `signal_instance_create_flow` redacts `raw` first, so `session_token` becomes `"[REDACTED]"`. `find_entities` then extracted that string as an entity value. Every instance got the same entity, and the deduplication filter on that entity type treated them all as duplicates and merged them into one case.

**The fix:** `find_entities` in `src/dispatch/entity/service.py` is the only place entities are built from a payload, and the flow, `entity_type/flows.py` and `entity_type/service.py` all go through it. It now does two things:
- It runs the JSONPath search on `redact_raw(signal_instance.raw)`, so a sensitive value never becomes an entity even if the stored payload hasn't been masked yet. That covers the window before the flow runs and older rows. The `entity_type/service.py` re-extraction path reads those stored payloads.
- It skips any match equal to `MASK`, so a payload that is already masked doesn't produce the shared `"[REDACTED]"` entity.

The masking itself is unchanged.

**Test:** I added `test_find_entities_ignores_masked_values` to `tests/entity/test_entity_service.py`. Its payload has a token, a nested `Password` and a normal `user` field. It checks that only `user` becomes an entity, both with an unredacted payload and with an already-masked one.

A payload that legitimately contains the literal string `[REDACTED]` in a non-sensitive field will also no longer produce an entity.

----- next turn -----

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