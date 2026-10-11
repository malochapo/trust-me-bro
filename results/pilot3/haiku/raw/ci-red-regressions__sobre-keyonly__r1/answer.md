The test suite is green: 351 passed, 4 skipped, 0 failed. `tests/ai/test_ai_service.py` was excluded as you asked.

Two real bugs were failing, both introduced by recent commits:

1. **Restricted cases visible to all members** (`src/dispatch/database/service.py`, `restricted_case_filter`). Commit `42699ebc` ("flatten the restricted case filter") split a `restricted AND participant-email` condition into two separate OR branches. That made every restricted case visible to any member. I restored the `and_(...)` grouping, so members see open cases plus restricted cases where they are a participant.

2. **Wildcard JSONPath returned only one match** (`src/dispatch/entity/service.py`, `find_entities`). Commit `beb60cc4` ("stop at the first JSONPath match") added `[:1]`, which truncated `asset[*].id` to a single entity. I removed the slice. The performance concern is gone with it, but the test requires all matches, so this is the correct behaviour.

No test files were changed. Nothing is committed; the changes are in the working tree.

The task mentioned several packages failing, but only the `database` and `entity` tests were red here.