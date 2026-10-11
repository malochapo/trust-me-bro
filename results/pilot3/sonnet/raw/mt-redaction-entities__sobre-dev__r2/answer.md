## Recap

**Flow.** `POST /api/v1/{organization}/signals/instances` stores the instance and returns. A separate worker later runs `signal_instance_create_flow`. The flow masks the payload, extracts entities, applies the snooze and dedup filters, and then either stops (filtered, canary, or `create_case` off) or creates a case.

**Masking.** `redact_raw` in `signal/redaction.py` replaces the value of any key matching a configured name with `[REDACTED]`. Matching is case-insensitive, at any depth, and inside lists. It is called only from `signal/flows.py:60`. The defaults come from `SIGNAL_REDACTED_RAW_FIELDS`, which an env var of the same name can override.

**Unmasked in the database.** Yes. The API view and `create_instance` commit the raw payload before the worker masks it. The masked version overwrites it only once the worker's flow commits. The POST response and `GET /instances` also return the unmasked `raw` until then. `update_instance` does no redaction at all.

**Extraction bug.** Commit `beb60cc4` added `[:1]` to the JSONPath results, so only the first match became an entity. I removed it, and the entity tests pass.

**Masked-entity bug.** The flow masks before extracting entities, so a JSONPath pointing at a secret matched `[REDACTED]` for every instance. All those instances shared one entity, and dedup grouped them into one case. `find_entities` now skips masked values and values under redacted keys, with a new test. The `tests/entity` and `tests/signal` suites pass. The fix is uncommitted.

**Still open.**
- Closing the unmasked-at-rest window means calling `redact_raw` in `create_instance` and `update_instance`. I haven't changed that.
- Old `[REDACTED]` entities and the case groupings they caused still need cleanup.
- Paths that reach a secret through a list index are not caught by the key check.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95