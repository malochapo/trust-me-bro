**Short answer:** the masking is done by `redact_raw()` in `signal/redaction.py`. It runs in the background processing flow, not in the API request. So the unmasked payload is written to the database first, and the API response also returns it unmasked. I traced this by reading the code. I didn't run anything.

## Trace

1. **`POST /instances`** is `create_signal_instance` in `signal/views.py:70`.
   - It resolves the project.
   - It finds the signal definition by external id or variant, then falls back to the project default. If none exists, it returns 404.
   - It calls `signal_service.create_instance(...)` and then `db_session.commit()`.
   - A duplicate id raises `IntegrityError`, which becomes a 409.
   - It returns the `SignalInstance` as `SignalInstanceRead`.
   - The view never calls the processing flow. `background_tasks` is a parameter, but nothing uses it.
2. **`signal_service.create_instance`** is at `signal/service.py:650`.
   - It builds the `SignalInstance` with `raw=json.loads(json.dumps(signal_instance_in.raw))`. That is a JSON round-trip of the original payload, with no masking.
   - It sets the id from `raw["id"]` and checks that it is a UUID.
   - It attaches case priority, case type and oncall service, then calls `db_session.add`.
3. **A separate worker picks the instance up later.**
   - The two callers of `signal_instance_create_flow` are `process_signal_batch` (`signal/flows.py:394`) and the signal consumer loop in `cli.py:1004`.
   - Both select instances where `filter_action IS NULL` and `case_id IS NULL`.
4. **`signal_instance_create_flow`** (`signal/flows.py:46`) does the following, in order:
   1. It loads the instance.
   2. It **masks the payload**: `signal_instance.raw = redact_raw(signal_instance.raw)` (line 60).
   3. It extracts entities from the signal's entity types plus the `all`-scoped ones. This now runs on the masked payload. It commits.
   4. It calls `signal_service.filter_signal(...)`. If a filter matches (dedupe, snooze and so on), it logs, updates the Slack signal message if a case already exists, and returns. **Filtered out.**
   5. If the instance is a canary, or `signal.create_case` is false, it stops with no case.
   6. Otherwise it resolves case type, priority, oncall assignee and conversation target, then calls `case_service.create` and links the case to the instance. It then runs `case_new_create_flow`, `engage_signal_identity` (if the signal has engagements) and any workflows. **Case opened.**

## Masking details

- **Function:** `redact_raw(raw, fields=SIGNAL_REDACTED_RAW_FIELDS)` calls the recursive helper `_redact`, both in `signal/redaction.py`.
- **What it does:** it replaces the value of any matching key with `"[REDACTED]"` and returns a copy.
  - Keys match case-insensitively, after trimming whitespace.
  - It matches at any depth, inside dicts and lists.
  - It matches key names only, never values.
  - It matches whole key names exactly, not substrings. For example, `db_password` is not masked.
- **Default keys** come from `SIGNAL_REDACTED_RAW_FIELDS` (`config.py:98`): `password`, `secret`, `api_key`, `session_token` and `authorization`. You can override them with the env var `SIGNAL_REDACTED_RAW_FIELDS`, as a comma-separated list.

## Is the unmasked payload written to the database?

Yes.
- `create_signal_instance` commits the unmasked `raw` in the request (`views.py:~110`).
- The row stays unmasked until the worker runs `signal_instance_create_flow`.
- If the worker errors, or never runs, the row stays unmasked. The worker rolls back on exceptions, and rows with `filter_action` and `case_id` both unset are retried.
- The masking only overwrites the stored value once the worker commits.
- The API response returns the instance, so the unmasked `raw` is also sent back to the caller.
- Only the `signal/flows.py` function `signal_instance_create_flow` calls `redact_raw`. The scheduler path `create_signal_instance` in `signal/flows.py` also stores `raw` unmasked, and it relies on the same later flow.
- `redact_raw` is never called in `create_instance`, in the view, or in the response serializer. Masking isn't applied before the `commit()` or on any other read path.
- I didn't check whether other tables or logs copy `raw`, such as a signal message or workflow input built before the flow runs.

## Unrelated issue in `views.py`

In `create_signal_instance`, if the request already supplies `signal_instance_in.signal`, then `signal_definition`, `external_id` and `variant` are never assigned. The `if not signal_definition` check that follows would then raise `NameError`. I didn't change anything.

If you want, I can sketch a fix that masks in `create_instance` or in the view, before the first commit.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") caused it. In `find_entities` in `src/dispatch/entity/service.py`, it changed `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. That kept only the first match for each entity type.

I reverted that line and removed the comment the commit added. The change is back to the original code, and I didn't touch the tests. `python -m pytest tests/entity` now passes, 11 tests.

The change was also only a small performance gain: `find` still evaluates every match before the slice.

----- next turn -----

**Why it happens.** `signal_instance_create_flow` masks `raw` before it extracts entities, which is what we saw in the first trace. Once the session token is masked, the entity type's JSONPath returns the literal `"[REDACTED]"`. Every instance of that signal then gets the same entity, `[REDACTED]`. The deduplication filter on that entity type sees them all as duplicates and groups unrelated instances into one case.

**Fix.** `src/dispatch/entity/service.py` is the one place entities are extracted. The signal flow, the entity-type service and the entity-type flow all call `find_entities`, so I fixed it there:
- A match equal to the mask (`MASK` from `dispatch/signal/redaction.py`) is never turned into an entity.
- `find_entities` now runs `redact_raw` on a copy of the payload before searching. The entity-type service and entity-type flow can pass an unmasked payload, because masking only happens in the signal flow. Without this, they could still make an entity out of the real secret.
- The masking itself is unchanged.

**Test.** I added `test_find_entities_ignores_masked_values` to `tests/entity/test_entity_service.py`. It covers an already-masked payload and an unmasked one with a real-looking token. In both cases only the non-secret `user` entity is returned. The `tests/entity` and `tests/signal` suites pass (44 passed, 1 skipped).

A JSONPath that points at a field with a masked key name, such as `password` or `api_key`, no longer produces entities anywhere. That follows from your requirement.

----- next turn -----

## Recap

**Intake path.** `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `signal/views.py`. It resolves the signal definition and calls `signal_service.create_instance`. That call stores `raw` exactly as received, and the view commits it. The instance is returned to the caller unmasked. A worker later calls `signal_instance_create_flow`, from `process_signal_batch` or the `cli.py` consumer loop. The flow does the following:
1. It masks `raw`.
2. It extracts entities.
3. It runs the filters. A filtered instance stops there.
4. A canary, or a signal with `create_case` off, also stops there.
5. Otherwise it opens a case.

**Masking.** `redact_raw` in `signal/redaction.py` replaces the value of any key named in `SIGNAL_REDACTED_RAW_FIELDS` with `[REDACTED]`. It matches key names, not values. Matching is case-insensitive and exact, at any depth, inside dicts and lists. The defaults are `password`, `secret`, `api_key`, `session_token` and `authorization`. They can be overridden with the env var of the same name.

**Unmasked data in the database.** Yes. The raw payload is committed unmasked at request time. It is overwritten with the masked copy only when the worker processes the instance. If the worker never runs, the unmasked payload stays in the database.

**Extraction bug.** Commit `beb60cc4` added `[:1]` to `jpath.find(...)`, so only the first JSONPath match became an entity. I reverted that line, and `tests/entity` passes.

**Grouping bug.** Masking runs before entity extraction. A JSONPath pointing at the session token therefore returned `[REDACTED]` for every instance, and the deduplication filter grouped them all together. I fixed `find_entities` in `entity/service.py`. It now masks a copy of the payload and never turns a masked value into an entity. I added a test for it. The `tests/entity` and `tests/signal` suites pass.

**Unfixed.** `create_signal_instance` can raise `NameError` when the request supplies `signal`. The unmasked-at-intake behaviour is also still in place. I didn't change either.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4