The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` excluded as you said. Two bugs were behind the failures, both introduced by recent commits.

1. **Restricted case filter** (`src/dispatch/database/service.py`): commit `42699ebc` ("flatten the restricted case filter") dropped the `and_`. Every restricted case therefore became visible to everyone, which is an access-control leak. I put back the `and_`, so a restricted case is visible only to a participant whose email matches the current user. This fixed `test_restricted_case_filter_with_test_data`.

2. **Entity JSONPath matching** (`src/dispatch/entity/service.py`): commit `beb60cc4` ("stop at the first JSONPath match") sliced the matches with `[:1]`. That broke wildcard paths like `asset[*].id`, which should return every match. I removed the slice. This fixed `test_find_entities_with_field_only`.

I didn't change any tests.