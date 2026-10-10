The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` ignored as you said. Two bugs caused the two failures.

- **Case visibility** (`src/dispatch/database/service.py`): `restricted_case_filter` listed `Visibility.restricted` as its own alternative. Members could therefore see every restricted case, not just the ones they take part in. I changed it to require a restricted case plus the user's participation, the same way `restricted_incident_filter` does.
- **Entity extraction** (`src/dispatch/entity/service.py`): commit `beb60cc4` ("stop at the first JSONPath match") added `[:1]` to `jpath.find(...)`. That dropped every match after the first, so `find_entities` returned 1 entity where the test expects 2. I removed the truncation.

I didn't touch any tests. I haven't committed anything.