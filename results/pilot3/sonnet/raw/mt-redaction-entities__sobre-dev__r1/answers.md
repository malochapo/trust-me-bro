The unmasked payload is written to the database. The masking runs later, in a separate worker step, so there is a window where the raw secrets are stored. I read the code only and ran nothing.

## Trace

1. **Request.** `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `signal/views.py:70`.
   - It resolves the project.
   - It finds the signal definition by `raw["externalId"]` or `raw["variant"]`, falls back to the project's default definition, and returns 404 if neither exists.
   - It calls `signal_service.create_instance`.
   - It then calls `db_session.commit()`.
   - A duplicate id returns 409 (`IntegrityError`).
   - It returns the `SignalInstance` as the response.

2. **Persist.** `create_instance` (`signal/service.py:650`) builds the `SignalInstance`.
   - `raw` is copied, then round-tripped through `json.loads(json.dumps(...))`.
   - `raw["id"]` becomes the primary key if present, and a non-UUID id returns 400.
   - It attaches the case type, case priority and oncall service, then runs `db_session.add`.
   - **No redaction happens here or in the view.**

3. **Handoff.** The view takes a `background_tasks` argument but never uses it. It doesn't call the flow itself. A separate worker picks the row up later. There are two entry points:
   - `process_organization_signals` in `signal/flows.py` (via `main_processing_loop`, which sleeps `LOOP_DELAY` = 60s between passes) selects rows from `signal_service.get_unprocessed_signal_instance_ids`.
   - A loop in `cli.py` (around line 990) selects `SignalInstance` rows with `filter_action IS NULL` and `case_id IS NULL`, oldest first, 500 at a time.
   - Both call `signal_instance_create_flow`, then commit.

4. **Flow** (`signal_instance_create_flow`, `signal/flows.py:44`):
   - **Masking.** Line 60 runs `signal_instance.raw = redact_raw(signal_instance.raw)`. Line 59 has a comment saying this happens before entities are extracted.
   - **Entities.** It gathers the signal's entity types plus the `all`-scoped ones. `entity_service.find_entities` runs JSONPath over `raw`, which is now the masked copy. It sets `signal_instance.entities` and commits.
   - **Filtering.** `signal_service.filter_signal` applies snooze and dedup filters.
     - If it returns true, the instance is filtered. The flow logs it, updates the Slack signal message when a case already exists, and returns.
     - The instance is not committed with a case when it is filtered.
   - **Early returns.** The flow also returns early for canary signals and for signals with `create_case` false. In both cases the instance is stored with no case.
   - **Case creation.** Otherwise it resolves the case type, priority, severity, oncall assignee and conversation target. It builds a `CaseCreate`, calls `case_service.create`, sets `signal_instance.case`, commits, then runs `case_flows.case_new_create_flow`.

## Masking details

- **Function:** `redact_raw` in `signal/redaction.py:10`, with the recursive helper `_redact`. It returns a new structure rather than mutating the input.
- **Matching:** key names, compared case-insensitively, at any depth, inside dicts and lists. It matches key names exactly, not substrings, so `db_password` or `Authorization-Token` would not be masked.
- **Replacement:** the value becomes `"[REDACTED]"`.
- **Default keys:** `password, secret, api_key, session_token, authorization`. These come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which the `SIGNAL_REDACTED_RAW_FIELDS` environment variable overrides as a comma-separated list. `redact_raw` strips whitespace and drops empty entries.

## Is the unmasked payload ever written to the database?

Yes. `SignalInstance.raw` is a JSONB column (`signal/models.py:239`). The view commits the unredacted payload at step 1, and it stays there until the worker runs. Two consequences:

- **Exposure window:** `GET /signals/instances` and the POST response itself return `raw` unmasked, and the stored data stays unmasked until the worker commits the masked copy. The worker only commits after masking succeeds, because `find_entities` commits after the masking line and each instance is committed afterwards.
- **Failures:** if the worker never picks the row up, or fails before the commit, the secrets remain stored. The worker's error path calls `rollback()`, so a masked change that wasn't yet committed is lost.

I also checked `signal_service.create_signal_instance`, a second creation path (`service.py:162`). It also calls `create_instance` without masking. Only the flow redacts.

To close the gap, I'd call `redact_raw` in `create_instance` (or the view) before the first commit, and keep the flow call as a backstop. I haven't changed anything.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") caused it. It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`. That kept only the first match for each entity type.

I reverted that line to `matches = jpath.find(signal_instance.raw)` and removed the comment that justified the truncation. The diff is exactly that one hunk, which restores the file to its state before the commit. `python -m pytest tests/entity` now passes (11 tests), and I didn't touch any tests. I haven't committed anything.

----- next turn -----

Unrelated instances were grouped because masking runs before entity extraction. `session_token` is one of the default masked keys, so the JSONPath on it matched `"[REDACTED]"` on every instance. That gave every instance of the signal the same entity value, and the deduplication filter treated them as duplicates and grouped them into one case.

Every extraction path goes through `find_entities` in `src/dispatch/entity/service.py`. Those paths are the signal flow, `entity_type/flows.py`, and the re-extraction in `entity_type/service.py`. I fixed it there. `find_entities` now skips any matched value equal to `MASK` (`"[REDACTED]"`, imported from `dispatch.signal.redaction`), so a masked value can't become an entity from any of them. The masking itself is unchanged.

I added `test_find_entities_skips_masked_values` to `tests/entity/test_entity_service.py`. It runs `redact_raw` on a payload with a top-level `session_token` and a nested `Password`, then checks that only the unmasked `user` value becomes an entity. `tests/entity` and `tests/signal` pass: 44 passed, 1 skipped. I didn't re-run the test before the fix, so I haven't seen it fail without the change. Nothing is committed. The working tree also still holds the earlier `[:1]` revert.

Skipping a literal `"[REDACTED]"` value also drops a payload that genuinely contains that string. I judged that acceptable, because a masked value and a literal one can't be told apart after masking.

----- next turn -----

## Recap

**Flow.** `POST /signals/instances` handles the request in `create_signal_instance` (`signal/views.py`). `create_instance` (`signal/service.py`) writes the payload to the database and the view commits it. The view doesn't run the processing flow. A worker later picks up unprocessed instances through `main_processing_loop` or the `cli.py` loop, and runs `signal_instance_create_flow`. That flow does the following:
- It masks `raw` with `redact_raw`.
- It extracts entities with `find_entities`.
- It applies the filters in `filter_signal`. A filtered instance is deduplicated or snoozed and gets no new case.
- Otherwise it creates a case, unless the signal is a canary or has `create_case` off.

**Masking.** `redact_raw` replaces the value of any key named in `SIGNAL_REDACTED_RAW_FIELDS` with `"[REDACTED]"`. Matching is by exact key name, case-insensitive, at any depth in dicts and lists. The environment variable `SIGNAL_REDACTED_RAW_FIELDS` overrides the defaults.

**Gap.** The unmasked payload is committed to the JSONB `raw` column at ingestion, before the worker masks it. The `GET /signals/instances` endpoint and the POST response both return it unmasked, and it stays that way until the worker commits the masked copy. The second creation path, `signal_service.create_signal_instance`, also doesn't mask. I proposed masking in `create_instance` but haven't made that change.

**Bugs found this session:**
- **First-match-only extraction:** commit `beb60cc4` truncated JSONPath matches with `[:1]`. I reverted that line and `tests/entity` passes.
- **Masked values becoming entities:** masking ran before extraction, so a JSONPath on `session_token` gave every instance the entity `"[REDACTED]"`, and deduplication grouped unrelated instances. `find_entities` now skips values equal to the mask. I added `test_find_entities_skips_masked_values`, and `tests/entity` and `tests/signal` pass.
- Both fixes are in the working tree and not committed.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95