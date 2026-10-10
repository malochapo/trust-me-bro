The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` excluded as you said. Two bugs were behind the failures:

1. **Restricted case visibility** (`src/dispatch/database/service.py`, `restricted_case_filter`): the `or_` had a bare `Case.visibility == restricted` clause, so members saw every restricted case. It now requires `restricted` and the user being a participant, matching `restricted_incident_filter`.
2. **Entity extraction** (`src/dispatch/entity/service.py`, `find_entities`): commit `beb60cc4` ("stop at the first JSONPath match") cut the matches to the first one with `[:1]`. That dropped legitimate additional matches, so I removed the truncation.

I made no test changes and no commits.