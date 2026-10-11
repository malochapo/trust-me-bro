The security review recap is below. The five result lines are at the end, in a code block so the format stays exact.

**Request path and masking**
- `POST /api/v1/{organization}/signals/instances` is handled by `create_signal_instance` in `src/dispatch/signal/views.py:70-129`. It creates the instance and commits it at `views.py:120`, before any masking happens.
- Masking runs later, in the background processing loop. `signal_instance_create_flow` in `src/dispatch/signal/flows.py:59-60` calls `redact_raw`, which is defined in `src/dispatch/signal/redaction.py`.
- It masks dict keys only, matched case-insensitively at any depth, with values replaced by `"[REDACTED]"`. It does not scan string values, and it does not match variants such as `apiKey` or `x-api-key`.
- The default keys come from `SIGNAL_REDACTED_RAW_FIELDS` in `src/dispatch/config.py:98-102`, and can be overridden by the environment variable of the same name.
- The unmasked payload is written to the database at the POST commit. The masked version overwrites it only when a later flow commit runs. If the flow fails, the redaction is rolled back and the unmasked payload stays in the row while the instance is retried.

**Extraction and the grouping bug**
- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath match in `find_entities`. That reduced every JSONPath entity type to one entity per signal. I reverted it. `tests/entity` now passes.
- Masked values became entities because `find_entities` ran on the masked payload in the normal flow, so the entity was `"[REDACTED]"`. The backfill in `entity_type/service.py:95` ran on the unmasked stored payload. Dedup groups by entity value, so unrelated token instances collapsed into one case.
- I fixed this in `find_entities`: it now searches a redacted copy of the payload and skips any match equal to the mask. Test `test_find_entities_never_returns_masked_values` was added. The masking in `redaction.py` and the flow is unchanged.

**Open items, not fixed**
- `signal/views.py:97` raises `UnboundLocalError` (a 500) when the request body includes `signal`, because `signal_definition` is never assigned on that path. I found this by reading the code and did not run it.
- `recalculate_entity_flow` in `entity_type/flows.py:26` assigns `entity_types` to the result of `.append(...)`, which is `None`, so it never extracts entities.

**Other notes**
- Changes are uncommitted: `src/dispatch/entity/service.py` and `tests/entity/test_entity_service.py`.
- `tests/signal` and `tests/entity_type` pass (38 passed, 1 skipped), along with `tests/entity` (12 of 12).

```
REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95
```