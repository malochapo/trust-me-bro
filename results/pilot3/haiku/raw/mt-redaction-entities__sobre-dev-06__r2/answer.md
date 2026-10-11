Here's the recap for the security review. Nothing is committed yet: the entity-extraction fix and the new test are uncommitted working-tree changes.

**Masking of the raw payload**
- Masking happens in `signal_instance_create_flow` (`src/dispatch/signal/flows.py:60`), before entity extraction. The view's POST handler does not mask anything.
- Matching is case-insensitive exact key equality at any depth, through dicts and lists. Substrings and `-` vs `_` variants are not matched, so `apiKey` and `x-api-key` are not masked by default.
- The unmasked payload is written to the database by the POST handler's commit, before the background flow runs. Instances that are never processed keep it unmasked. The masked copy overwrites it at the next commit in the flow.
- `update_instance` (`src/dispatch/signal/service.py:726`) also writes `raw` without masking. Nothing in `src/` calls it today.

**Entity extraction**
- `beb60cc4` added `[:1]` to the JSONPath match, so only the first match became an entity. That broke `test_find_entities_with_field_only`. I reverted it.
- Masked values were becoming entities: every instance shared the value `[REDACTED]`, and the dedup filter grouped them. I fixed this in `_find_entities_by_jsonpath_expression` (`src/dispatch/entity/service.py`) by skipping values equal to `MASK`. I added `test_find_entities_ignores_masked_values`, which fails without the fix and passes with it.
- Entities already created from `[REDACTED]` remain in the database. Deleting them and re-running extraction needs a data decision, so I haven't done it.

Verification: `python -m pytest tests/entity tests/signal tests/entity_type` passes (50 passed, 1 skipped).

REDACTION_FUNCTION: dispatch.signal.redaction.redact_raw
DEFAULT_KEYS: password,secret,api_key,session_token,authorization
UNMASKED_IN_DATABASE: yes
EXTRACTION_BUG: beb60cc49435f38d6296e1607b07f6dff31804b1
MASKING_COMMIT: d2675cf4b078246ae14df279469af513b348ab95