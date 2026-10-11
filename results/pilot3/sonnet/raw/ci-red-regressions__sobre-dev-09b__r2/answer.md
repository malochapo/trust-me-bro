The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` excluded as you said. No tests were changed. Two bugs were behind the failures.

- **Restricted case visibility** (`src/dispatch/database/service.py`, `restricted_case_filter`): the filter let members see every restricted case, because the participant check was `or`'d in at the top level instead of being scoped to restricted cases. I wrapped it in `and_(restricted, participant email matches)`, which is how `restricted_incident_filter` already works. This fixed `test_restricted_case_filter_with_test_data`.
- **Entity extraction** (`src/dispatch/entity/service.py`, `find_entities`): a recent "perf" commit cut each JSONPath's matches to the first one (`[:1]`). That broke wildcard paths like `asset[*].id`, which should yield every match. I removed the truncation, which fixed `test_find_entities_with_field_only`.

I haven't committed anything.