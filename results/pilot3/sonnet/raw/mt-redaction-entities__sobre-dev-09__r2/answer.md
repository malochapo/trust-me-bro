**Recap**

- **Request path:** `POST /api/v1/{organization}/signals/instances` (`signal/views.py:70`) resolves the signal definition and calls `signal_service.create_instance`. It then commits the instance with its raw payload exactly as received.
- **Worker:** the `signals consume` loop in `cli.py` later picks up instances that have no `filter_action` and no `case_id`. It runs `signal_instance_create_flow` on each one.
- **Masking:** the first thing the flow does is `signal_instance.raw = redact_raw(signal_instance.raw)` (`signal/flows.py:60`). `redact_raw` matches key names case-insensitively at any depth and replaces their values with `"[REDACTED]"`.
- **What happens next:** entities are extracted, then snooze and dedup filters run. An instance ends in one of these ways:
  - filtered out (snoozed or deduplicated);
  - stored as a canary;
  - stored with no case because the signal has `create_case` off;
  - turned into a case.
- **Database exposure:** the API commits the unmasked payload before any masking runs. It stays in the database until the worker commits the masked copy. If the worker is down or the flow fails before its commit, it stays unmasked indefinitely. `update_instance` and the scheduler's `create_signal_instance` helper never redact.
- **Extraction bug:** commit `beb60cc4` added `[:1]` to the JSONPath matches in `find_entities`, so only the first match per entity type was kept. I reverted that line.
- **Grouping bug:** extraction ran on already-masked payloads, so every instance got an entity with the value `"[REDACTED]"`. The dedup filter then grouped unrelated instances. `find_entities` now skips masked values, and `test_find_entities_skips_masked_values` covers it.
- **Status:** the fixes and the new test are uncommitted. `tests/entity` and `tests/signal` pass.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc4
MASKING_COMMIT: d2675cf4