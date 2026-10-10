The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` ignored as you said. Only two tests were failing, both in the last few days' commits, and I didn't touch any tests.

- **Restricted case visibility** (`src/dispatch/database/service.py`): commit `42699ebc`, which flattened the filter, turned the `and_` into a plain `or_` list. As a result, every restricted case was visible to any member, not just participants. I restored the `and_(restricted, participant email matches)` condition in `restricted_case_filter`. This fixes `test_restricted_case_filter_with_test_data`.
- **Entity JSONPath matching** (`src/dispatch/entity/service.py`): commit `beb60cc4`, the "stop at the first JSONPath match" perf change, sliced `jpath.find(...)` to `[:1]`. That dropped every match after the first, so only one entity was created where the test expects two. I removed the slice. This fixes `test_find_entities_with_field_only`.

I haven't committed anything.