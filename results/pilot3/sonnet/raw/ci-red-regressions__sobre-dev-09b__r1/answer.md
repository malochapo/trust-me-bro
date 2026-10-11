The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` ignored as you said. Two bugs were behind the failures, and I didn't change any tests.

- **Restricted case visibility** (`src/dispatch/database/service.py`): `restricted_case_filter` treated "restricted" and "user is a participant" as separate OR conditions. A member could therefore see every restricted case. It now requires restricted visibility and a participant match together, the same way `restricted_incident_filter` does.
- **Entity extraction** (`src/dispatch/entity/service.py`): the recent perf commit `beb60cc4` ("stop at the first JSONPath match") cut each JSONPath's results to the first match with `[:1]`. That dropped the other matching entities. I removed the slice, so every match is returned again.

Removing the slice undoes that perf commit's intent. If you still want the speed-up, it would need a different approach that keeps all matches.