The suite is green: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` excluded as you asked. The two failures were regressions from this week's commits, and I fixed the code in both places without touching any tests.

1. **Restricted case visibility** (`src/dispatch/database/service.py`, `restricted_case_filter`). Commit `42699ebc` "flatten the restricted case filter" removed an `and_` so the filter became `open OR restricted OR email matches`. That let members see every restricted case. I restored the `and_`, so restricted cases are visible only to a participant whose email matches the user.

2. **JSONPath matching** (`src/dispatch/entity/service.py`, `_find_entities_by_jsonpath_expression`). Commit `beb60cc4` "stop at the first JSONPath match" added `[:1]` to `jpath.find(...)`. That truncated wildcard paths like `asset[*].id`, which should yield every match. I removed the slice. The perf gain was only real for paths that already match at most once, so it is gone. If you want the optimization back, it would need to stop early only for non-wildcard paths.

I haven't committed anything. The changes are in the working tree for you to review.