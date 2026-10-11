The suite is green: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` excluded as you asked. Two tests were failing, each from a bug in a recent commit, and I fixed both in source without touching any tests.

1. **Restricted case filter** (`src/dispatch/database/service.py`, `restricted_case_filter`): commit `42699ebc` "flattened" the filter by removing an `and_` around the restricted clause. That made the condition `open OR restricted OR participant-email-matches`, so members saw every restricted case. I restored the grouping so a restricted case is visible only when the user is a participant.

2. **Entity extraction** (`src/dispatch/entity/service.py`, `find_entities`): commit `beb60cc4` added `[:1]` to the JSONPath matches, on the premise that a JSONPath "names one field". That's wrong for wildcard paths like `asset[*].id`, which legitimately match several values, so only the first was kept. I reverted that line; the intended perf gain would need a different approach if you still want it.

Both changes are uncommitted in the working tree. I didn't commit, since you didn't ask for one.