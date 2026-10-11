The suite is green: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` excluded as you asked. I changed no tests.

Two real regressions were behind the two failing tests:

- **Restricted cases visible to all members** (`src/dispatch/database/service.py`, `restricted_case_filter`): commit `42699ebc` ("flatten the restricted case filter") dropped the `and_(...)` around the restricted branch. Restricted cases then matched for any member, not just participants. I restored the `and_`, which matches how `restricted_incident_filter` is written.
- **Wildcard JSONPath returned one match** (`src/dispatch/entity/service.py`, `find_entities`): commit `beb60cc4` ("stop at the first JSONPath match") added `[:1]`, so `asset[*].id` yielded only one entity. That slice is gone, so every match is extracted again. The perf gain from the early stop is lost with it. I didn't try to keep it for non-wildcard paths; if you want that optimization back, it needs its own change that leaves wildcard results intact.

Only two packages were failing locally, not "several". The other CI failures you saw may come from environments I can't reproduce here.