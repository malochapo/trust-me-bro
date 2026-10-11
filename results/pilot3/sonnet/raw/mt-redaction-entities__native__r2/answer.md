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