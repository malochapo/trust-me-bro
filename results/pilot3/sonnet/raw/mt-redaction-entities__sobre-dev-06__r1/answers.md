I've traced the whole path and have what I need, so I'm writing it up now.

## Trace of `POST /api/v1/{organization}/signals/instances`

1. **Endpoint:** `create_signal_instance` in `signal/views.py:70`.
   - It resolves the project.
   - It finds the signal definition by `externalId` or `variant` in the raw payload, then falls back to the project's default definition, then returns a 404.
   - It calls `signal_service.create_instance` and then `db_session.commit()`.
   - It does not run the create flow. The `background_tasks` parameter is unused.
2. **Persist:** `signal/service.py:650` builds the `SignalInstance` with `raw=json.loads(json.dumps(signal_instance_in_raw))`. This is a copy of the incoming payload with no masking, and it is added to the session. A duplicate id returns a 409.
3. **Pick-up:** the instance is saved with `filter_action=None` and `case_id=None`. The background loop in `signal/flows.py` (`process_organization_signals`, then `process_signal_batch`) finds it through `get_unprocessed_signal_instance_ids`. It calls `signal_instance_create_flow` (`flows.py:46`) and commits after each instance. `cli.py:1004` calls the same flow.
4. **Masking:** `flows.py:60` runs `signal_instance.raw = redact_raw(signal_instance.raw)`. This is the first step of the flow, before entity extraction.
5. **Entities:** entity types from the signal plus the `all`-scope types are applied with `entity_service.find_entities`, followed by a commit.
6. **Filtering:** `signal_service.filter_signal` runs snooze first, then dedup, and commits.
   - If a filter matched, the flow logs it, updates the Slack signal message if there is a case and conversation, and returns. No new case is created.
   - Canary signals, and signals with `create_case` off, are stored and the flow returns.
7. **Case:** otherwise the flow resolves case type, priority, severity, oncall assignee and conversation target. It then calls `case_service.create`, sets `signal_instance.case`, commits, and continues into the case-creation flow.

## Masking details

- **Function:** `redact_raw` in `signal/redaction.py:10`, with the recursive helper `_redact`.
- **Behavior:** it returns a copy where the value of any matching key becomes `"[REDACTED]"`.
  - Matching is case-insensitive.
  - It applies at any depth, inside dicts and lists.
  - Non-container values pass through unchanged.
- **Default keys:** `password`, `secret`, `api_key`, `session_token`, `authorization`. These come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98`, which is overridable through the env var of the same name as a comma-separated list.
- **Limits:** matching is exact on the whole key name, not a substring. `db_password` and `x-api-key` are not masked, and neither is a secret that appears as a value rather than a key.

## Is the unmasked payload written to the database?

Yes. The API handler commits the original `raw` at `views.py:119` (`create_instance` plus `commit`), before any redaction runs. The row holds the plaintext until the background worker processes it. The redacted `raw` only replaces it when the flow next commits, which is in `find_entities` or `filter_signal` (always), or in the worker's per-instance commit.

Consequences:
- **Exposure window:** the plaintext is in the database for as long as the worker takes to pick the instance up. The loop delay is 60 seconds, plus any batch backlog.
- **Failures:** if the flow raises before its commit, the worker rolls back and the redaction is lost. The row stays unprocessed, with plaintext, and is retried.
- **Reads:** `GET /instances` can return plaintext during that window.
- **Backups and replicas:** these can capture the plaintext, as can any DB-level audit log or WAL.

The plaintext is also in memory inside `create_instance`, and in the request-scoped `signal_instance_in`.

## Unrelated issue in `views.py`

If the request already supplies `signal_instance_in.signal`, then `signal_definition`, `external_id` and `variant` are never assigned. The `if not signal_definition` check below would raise `UnboundLocalError`.

I haven't changed any code. If you want to close the plaintext window, the fix would be to call `redact_raw` in `create_instance` (or the view) before the first commit.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") caused it. In `find_entities` in `src/dispatch/entity/service.py`, it changed `jpath.find(signal_instance.raw)` to `jpath.find(signal_instance.raw)[:1]`. A JSONPath that matches several fields, such as a wildcard or a recursive descent, then produced only one entity.

I reverted that line and removed the comment that justified it. `python -m pytest tests/entity` now passes (11 passed). I didn't touch the tests, and I haven't committed anything.

The commit was presented as a performance change, but it silently dropped data. If speed is the concern, the cost of `find` is in evaluating the path, so slicing the result afterwards saves almost nothing.

----- next turn -----

**Cause.** `signal_instance_create_flow` masks `raw` before it extracts entities. For the "GitHub: Personal access token exposed" signal, the JSONPath pointing at `session_token` therefore returned the literal `[REDACTED]` for every instance. All instances got the same entity, and the dedup filter on that entity type grouped them into one case.

**Fix.** The fix is in `find_entities` in `src/dispatch/entity/service.py`. That function is the only place entities are extracted from a payload. It now skips any matched value equal to `MASK`, which it imports from `signal/redaction.py`. Because the check is in `find_entities` itself, it covers every caller. The masking code is unchanged.

**Test.** I added `test_find_entities_skips_masked_values` to `tests/entity/test_entity_service.py`. It masks a payload containing `session_token` and a nested `Password`, then checks that only the unmasked `user` value becomes an entity. `tests/entity` and `tests/signal` pass (44 passed, 1 skipped). I didn't run the rest of the suite, and I didn't commit.

**Side effect.** Instances of that signal no longer get a session-token entity. A dedup filter on that entity type will now not match, which is the intended outcome since the real value is never kept.

**Limit.** The check only catches a value that is exactly `[REDACTED]`. A real payload value with that text would also be skipped, which I judged acceptable.

The unrelated issue I flagged earlier is still open: the plaintext payload is committed to the database before masking runs.

----- next turn -----

## Recap

**Flow.** `POST /signals/instances` (`signal/views.py`) finds the signal definition, saves the instance with `raw` exactly as sent, and commits. A background worker later runs `signal_instance_create_flow` (`signal/flows.py`).

The flow does these steps in order:
1. It masks `raw`.
2. It extracts entities.
3. It applies the snooze and dedup filters. If a filter matches, the instance is stored without a new case.
4. Otherwise it creates a case, unless the signal is a canary or has `create_case` off.

**Masking.** `redact_raw` in `signal/redaction.py` replaces the value of any matching key with `[REDACTED]`. Matching is case-insensitive, applies at any depth, and is exact on the key name. The keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py`.

**Unmasked payload in the database.** Yes. The API handler commits the plaintext `raw` before the worker masks it. The plaintext stays in the row until the worker next commits, and longer if the flow fails and is rolled back.

**Bug 1: only the first match became an entity.** Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath results in `find_entities`. I reverted that line, and `tests/entity` passes again.

**Bug 2: unrelated instances grouped into one case.** Masking runs before entity extraction. The `session_token` JSONPath therefore returned `[REDACTED]` for every instance, and the dedup filter grouped them. `find_entities` now skips masked values. I added `test_find_entities_skips_masked_values`.

**Not yet fixed.**
- The plaintext-in-database window.
- `views.py` raises `UnboundLocalError` when the request already supplies a `signal`.

Both code fixes are uncommitted in the working tree. The masking was introduced by `d2675cf4`, "feat(signal): mask sensitive raw fields before processing".

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95