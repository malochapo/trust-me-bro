The suite is green: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` left out as you said. Two bugs were behind the failures, and I didn't touch any tests.

1. **Restricted case visibility** (`src/dispatch/database/service.py`, `restricted_case_filter`): the filter ORed `visibility == restricted` with the participant email check. Every restricted case was therefore visible to every member, which is a permissions leak. I changed it to `and_(visibility == restricted, email == current_user.email)`. That matches `restricted_incident_filter`.
2. **Entity matching** (`src/dispatch/entity/service.py`, `find_entities`): commit `beb60cc4` ("stop at the first JSONPath match") sliced the results with `[:1]`. A path like `asset[*].id` then returned one entity instead of all its matches. I removed the slice.

I haven't committed anything.