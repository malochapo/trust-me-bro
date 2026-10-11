The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` excluded as you said. I didn't touch any tests. Two bugs caused the failures.

- **Case visibility filter** (`src/dispatch/database/service.py`): `restricted_case_filter` had its restricted-case condition flattened into the top-level `or_`. Members saw every restricted case, and anyone who was a participant on any case matched too. I wrapped it back into `and_(restricted, participant email matches)`, the same shape `restricted_incident_filter` already uses. This fixed `test_restricted_case_filter_with_test_data`.
- **Entity extraction** (`src/dispatch/entity/service.py`): the "stop at the first JSONPath match" perf change (`beb60cc4`) truncated `jpath.find(...)` to `[:1]`. A path can legitimately match several values, for example a wildcard over a list, so entities were silently dropped. I reverted that slice, which fixed `test_find_entities_with_field_only`.

I haven't committed anything.