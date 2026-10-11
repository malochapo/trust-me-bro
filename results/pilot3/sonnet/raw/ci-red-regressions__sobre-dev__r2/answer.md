The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` ignored as you said. Two bugs were behind the failures, and I didn't touch any tests.

1. **Case visibility filter** (`src/dispatch/database/service.py`, `restricted_case_filter`): the filter treated "restricted case" and "user is a participant" as separate OR conditions. Every restricted case was therefore visible to every member. I grouped them with `and_(...)`, so a restricted case is visible only to its participants. This now matches `restricted_incident_filter`.
2. **Entity extraction** (`src/dispatch/entity/service.py`, `find_entities`): the recent "perf" commit `beb60cc4` added `[:1]`, which kept only the first JSONPath match. A path like `asset[*].id` therefore returned one entity instead of two. I removed it.

I did not look for other callers that might depend on the first-match-only behaviour.