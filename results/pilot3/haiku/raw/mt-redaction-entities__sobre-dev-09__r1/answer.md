Recap of this session's work. Nothing is committed; the changes are in the working tree.

**1. Signal instance path and masking (question 1)**

- `POST /api/v1/{org}/signals/instances` is handled by `create_signal_instance` in `src/dispatch/signal/views.py`. It calls `signal_service.create_instance`, which stores the payload as received, and commits. It does not run masking and does not enqueue processing.
- Masking runs later, in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`), inside the background processing loop (`signals process`).
- After masking, the flow runs entity extraction, then `filter_signal` (snooze, then dedup). Instances that are not filtered and have `create_case` set get a case. Canary instances and instances with `create_case` off are stored without one.
- The unmasked payload is written to the database during the POST. The masked copy overwrites it once processing succeeds. If processing fails, the unmasked value stays in place and the row is retried.

**2. Entity extraction bug (question 2)**

- Commit `beb60cc4` ("perf(entity): stop at the first JSONPath match") added `[:1]` to the JSONPath match in `find_entities`. Each entity type then produced at most one entity. I reverted that line. `tests/entity` passes (11 of 11).

**3. Masked values becoming entities (question 3)**

- The masking step replaced the token with `"[REDACTED]"`, and entity extraction then stored that string as an entity. Every instance with a masked token shared one entity row, so the dedup filter grouped unrelated instances into one case.
- Fix: `_find_entities_by_jsonpath_expression` skips any match equal to `MASK`. That function is the only place JSONPath matches become entities, so the guard covers every extraction path, including the entity-type re-extraction in `entity_type/flows.py` and `entity_type/service.py`.
- Test added: `test_find_entities_never_extracts_masked_values` in `tests/entity/test_entity_service.py`. It failed before the guard and passes after. Masking itself is unchanged.
- Results: `tests/entity` and `tests/signal` pass (44 passed, 1 skipped).

**Open items**

- Entities already stored with the value `"[REDACTED]"` remain in the database, with their instances attached. Cleaning them up is a data decision, so I did not touch them.
- The scheduler ingest path (`create_signal_instance` in `flows.py`) also stores the raw payload unmasked, the same way the POST does. I did not change that, since you asked me to keep masking as it is.

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95