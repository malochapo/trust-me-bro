I've traced the whole path. The answer to your last question is yes: the unmasked payload is written to the database first. Masking only happens afterwards, in a separate asynchronous step.

**1. Request handling.** `create_signal_instance` in `signal/views.py:70` handles the POST.
- It resolves the project, then looks up the signal definition by `externalId` or `variant`.
- If neither matches, it falls back to the project's default signal definition. If there is no default, it returns 404.
- It calls `signal_service.create_instance` (`signal/service.py:650`), which builds the `SignalInstance` with `raw=json.loads(json.dumps(raw))`. That round trip only normalises dates, and nothing is masked.
- It then calls `db_session.add(...)`, and the view calls `db_session.commit()`. A duplicate id gives 409.
- The view returns with no filtering, no case creation and no masking. `background_tasks` is accepted but never used.

**2. Asynchronous processing.** Nothing is triggered by the request itself. A scheduler picks up unprocessed instances, meaning those with `filter_action` and `case_id` both null.
- `process_organization_signals` and `process_signal_batch` in `signal/flows.py:~395–420` do this, and so does a loop in `cli.py:~1004`.
- Each of them calls `signal_instance_create_flow` (`signal/flows.py:~44`).

**3. Masking.**
- **Where:** `signal_instance_create_flow` does it at `signal/flows.py:60`, with `signal_instance.raw = redact_raw(signal_instance.raw)`. It runs before entity extraction.
- **Function:** `redact_raw` in `signal/redaction.py`, which recurses through `_redact`.
  - It returns a copy.
  - It replaces the value of any matching key with `"[REDACTED]"`.
  - Matching is case-insensitive, at any depth, inside dicts and lists.
  - Non-dict and non-list values pass through unchanged.
  - Only values under matching keys are masked. Sensitive text embedded in other values is not.
- **Default keys:** `SIGNAL_REDACTED_RAW_FIELDS` in `config.py:98` defaults to `password,secret,api_key,session_token,authorization`. The `SIGNAL_REDACTED_RAW_FIELDS` env var overrides it with a comma-separated list.
- **Matching is exact on the key name.** `client_secret`, `token` and `apiKey` are not masked by default.

**4. After masking.**
- Entities are extracted from the masked payload and committed.
- `filter_signal` (`signal/service.py:866`) applies snooze, then dedup, and commits.
  - If either filters the instance, the flow returns. A deduplicated instance is attached to the existing case, and the Slack signal message may be updated.
  - Otherwise `filter_action` is set to `none`.
- A canary signal, or a signal with `create_case` off, is stored and the flow returns.
- Otherwise the flow resolves case type, priority, oncall and conversation target, then creates the case. It links the case to the instance and runs `case_new_create_flow`. Finally it runs engagements and workflows.

**5. Unmasked payload in the database: yes, in two ways.**
- The view commits the raw payload to the database at POST time, before any masking.
  - It stays that way until the scheduler runs the flow, which can take up to about a minute (`LOOP_DELAY = 60`).
  - `GET /instances` doesn't mask anything, so it can return the unmasked payload in that window.
- If the flow raises before the later commit, `process_signal_batch` rolls back, so the instance may stay unmasked and be retried.
  - Even on success, the masked `raw` is only committed by the later commit (the entity commit, `filter_signal`, or the batch commit), and any other copies or history in the database are not rewritten.

**6. Other paths.**
- The AWS plugin calls `create_signal_instance` (`plugins/dispatch_aws/plugin.py:113`). It goes through the same store-then-process pattern.
- The log line in the view logs only ids, not the payload.

Fixing the window would mean calling `redact_raw` in `create_instance` or in the view, before `db_session.add`. I haven't changed any code.

----- next turn -----

Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") caused the bug. It changed `find_entities` in `src/dispatch/entity/service.py` to `jpath.find(signal_instance.raw)[:1]`. That kept only the first match for each entity type.

I reverted that line to `jpath.find(signal_instance.raw)`, so every match becomes an entity again. The result is the same file content as before that commit. `python -m pytest tests/entity` now passes (11 passed), and I didn't touch any tests. The change isn't committed.

----- next turn -----

The fix is in and tested, and nothing is committed. The cause is the masking order I described in the first trace. The flow masks `raw` before it extracts entities, so every instance's session token becomes the literal `"[REDACTED]"`. `find_entities` then made an entity with that value for each instance. The dedup filter on that entity type saw them all as the same entity and grouped unrelated instances into one case.

**Fix:** `find_entities` in `src/dispatch/entity/service.py` now skips any JSONPath match whose value equals `MASK` from `signal/redaction.py`. I put it there because it is the only place entities are extracted from a payload.
- `signal_instance_create_flow` and the entity-type recalculation flow in `entity_type/flows.py` both go through it.
- The recalculation flow also reads stored payloads that were already masked.
- I left the masking itself unchanged.

**Test:** I added `test_find_entities_skips_masked_values` to `tests/entity/test_entity_service.py`. It masks a payload with `redact_raw` and checks that only the unmasked `actor` value becomes an entity, not the `session_token`. I didn't change any existing tests. I didn't run the new test against the unfixed code to confirm it fails there.

**Tests:** `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**Limits:**
- The check is on the exact string `"[REDACTED]"`. A payload that genuinely contains that string is skipped too, which seems acceptable.
- Instances that were already processed keep the `"[REDACTED]"` entities they got before this fix. Those entities, and any cases already grouped through them, are not cleaned up.

----- next turn -----

**Recap**

- **Flow:**
  - `POST /api/v1/{organization}/signals/instances` (`signal/views.py`) resolves the signal definition and stores the instance, then commits.
  - It does not mask, filter or create a case at that point.
  - A scheduler later picks up instances with no filter action and no case, and runs `signal_instance_create_flow`.
  - That flow masks the payload, extracts entities and runs `filter_signal` (snooze, then dedup). It then either stops, because the instance was filtered or is a canary or the signal has case creation off, or it creates a case.
- **Masking:**
  - `redact_raw` runs at `signal/flows.py:60`, before entity extraction.
  - It matches key names case-insensitively at any depth and replaces their values with `"[REDACTED]"`.
  - The default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `config.py`, which an environment variable can override.
  - Matching is by exact key name. `client_secret` and `apiKey`, for example, are not masked by default.
- **Unmasked payload in the database:** yes. The view commits the raw payload before any masking. It stays that way until the scheduler runs the flow, and `GET /instances` can return it in that window. If the flow fails and rolls back, the payload can stay unmasked. Moving the `redact_raw` call into `create_instance` or the view would close this. I haven't done that.
- **Extraction bug:** commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") sliced the matches to `[:1]`. I reverted that line.
- **Grouping bug:** extraction ran after masking, so every instance got an entity with the value `"[REDACTED]"`, and the dedup filter grouped unrelated instances. `find_entities` now skips masked values. I added a test, and the entity and signal tests pass. Entities created before the fix, and the cases grouped through them, are not cleaned up.

Both code changes are uncommitted.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4