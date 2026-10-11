The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` ignored as you said. Two bugs were behind the failures, and I didn't touch any tests.

- **Restricted case visibility** (`src/dispatch/database/service.py`, `restricted_case_filter`): the filter let every restricted case through, because the condition was `open OR restricted OR email matches`. It now matches the incident filter: a case is visible if it is open, or if it is restricted and the user is a participant. This fixed `test_restricted_case_filter_with_test_data`.
- **Entity extraction** (`src/dispatch/entity/service.py`, `find_entities`): the recent perf commit `beb60cc4` cut the JSONPath results down to the first match with `[:1]`. That dropped the other entities when a path matched several values. I removed the truncation. This fixed `test_find_entities_with_field_only`.

I haven't committed anything.