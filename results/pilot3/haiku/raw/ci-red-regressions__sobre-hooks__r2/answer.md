The suite is green locally: 351 passed, 4 skipped, 0 failed. I ignored `tests/ai/test_ai_service.py` as you asked. I did not touch any tests.

Two failures, each caused by a recent commit:

1. **Restricted case visibility** (`src/dispatch/database/service.py`, `restricted_case_filter`). Commit `42699ebc` ("flatten the restricted case filter") removed the `and_(...)` around the restricted-visibility check. That made every restricted case visible to members, not just the ones where they are a participant. I restored the grouping, so the condition is again "open, or restricted and the user is a participant."

2. **JSONPath matches** (`src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression`). Commit `beb60cc4` ("stop at the first JSONPath match") added `[:1]` to `jpath.find(...)`. That silently dropped every match after the first, so wildcard paths like `asset[*].id` produced one entity instead of two. I reverted the slice and its comment. This gives up the perf gain from that commit, which is the trade-off of keeping wildcard paths correct.

The four skipped tests are marked unconditional skips, or skipped on a validation error in the test itself. I didn't change them.

Nothing is committed.