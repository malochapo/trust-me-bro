The suite is green: 351 passed, 4 skipped, 0 failed. I ran it with `tests/ai/test_ai_service.py` excluded, as you asked. I did not commit.

There were two failures, each from a real bug, and I fixed the code rather than the tests:

1. **Member case visibility leak** (`src/dispatch/database/service.py`, `restricted_case_filter`). Refactor `42699ebc` flattened the `and_(...)` so that the `OR` clause read `visibility == restricted` on its own. Any member could then see every restricted case. I restored the `and_`, so restricted cases are only visible to members who are participants.

2. **Wildcard JSONPath entities dropped** (`src/dispatch/entity/service.py`, `find_entities`). Commit `beb60cc4` added `[:1]` to `jpath.find(...)` on the premise that a JSONPath names one field. That's false for wildcards like `asset[*].id`, which should yield every match. I removed the slice. This gives up the early-exit performance gain from that commit, which is the cost of matching the expected behaviour.

The CI report mentioned failures across several packages, but locally only these two tests failed. If CI shows others, they may depend on the network or on environment differences I can't reproduce here.