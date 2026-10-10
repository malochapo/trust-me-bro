The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` excluded as you said. Two bugs were behind the failures, and I didn't touch any tests.

1. **Restricted case visibility** (`src/dispatch/database/service.py`, `restricted_case_filter`): the filter let a member see every restricted case. The participant-email check had been put in the `or_` as its own alternative instead of being combined with `visibility == restricted`. I wrapped the two conditions in `and_`, which matches `restricted_incident_filter`. This fixed `test_restricted_case_filter_with_test_data`.

2. **Entity extraction** (`src/dispatch/entity/service.py`, `find_entities`): the recent "stop at the first JSONPath match" perf change sliced the results with `[:1]`. A path like `asset[*].id` then produced only one entity instead of one per match. I reverted that line, which fixed `test_find_entities_with_field_only`.

The entity fix gives up the performance change from `beb60cc4`. If you still want that optimisation, it would need to be done without dropping matches from wildcard paths.

I haven't committed anything.