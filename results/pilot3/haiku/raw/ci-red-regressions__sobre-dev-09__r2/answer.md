The suite is green: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` excluded as you asked. Two source bugs were behind the two failures, and I changed no tests.

1. **Restricted case visibility** (`src/dispatch/database/service.py`, `restricted_case_filter`): commit `42699ebc` ("flatten the restricted case filter") removed the `and_(...)` around the restricted-visibility check. As a result, members saw every restricted case, not only those they participate in. I restored the `and_` so restricted cases require the user to be a participant.

2. **Entity extraction** (`src/dispatch/entity/service.py`, `find_entities`): commit `beb60cc4` ("stop at the first JSONPath match") added `[:1]`, which dropped every match after the first. A JSONPath like `asset[*].id` legitimately produces several entities. I removed the slice so all matches are returned again. The performance rationale for that commit is lost with this change, so if the speedup was wanted, it needs a different approach that keeps all matches.

The changes are uncommitted in the working tree.