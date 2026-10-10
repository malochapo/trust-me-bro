The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` excluded as you said. Two bugs were behind the failures, and I didn't touch any tests.

1. **Restricted-case visibility** (`src/dispatch/database/service.py`, `restricted_case_filter`): The filter was missing an `and_`. It let non-admin users see every restricted case, and it also let them see any case where they were a participant. It now matches the incident filter: open cases, or restricted cases where the user is a participant. This fixed `test_restricted_case_filter_with_test_data`.

2. **Entity extraction** (`src/dispatch/entity/service.py`, `find_entities`): Commit `beb60cc4` ("stop at the first JSONPath match") added `[:1]`, which dropped all but the first match. A JSONPath with a wildcard can legitimately match several fields, so entities were being lost. I removed the truncation. This fixed `test_find_entities_with_field_only`.

Reverting that commit's change means `find_entities` goes back to processing every JSONPath match, so the speed-up that commit was after is gone.

I haven't committed anything.