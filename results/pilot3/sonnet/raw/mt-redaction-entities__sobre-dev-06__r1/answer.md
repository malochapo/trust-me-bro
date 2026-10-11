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