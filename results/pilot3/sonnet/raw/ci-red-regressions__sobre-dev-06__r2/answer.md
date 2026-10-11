The suite is green again: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` ignored as you said. Two bugs were behind the failures, and I didn't touch any tests.

- **Restricted case visibility** (`src/dispatch/database/service.py`): `restricted_case_filter` put the restricted-case check and the participant-email check in separate `or_` branches. Every restricted case was therefore visible to every non-admin user. I changed it to `and_(restricted, participant email matches)`, which is how `restricted_incident_filter` already works. This fixed `test_restricted_case_filter_with_test_data`.
- **Entity extraction** (`src/dispatch/entity/service.py`): commit `beb60cc4`, the "perf" change, cut `jpath.find(...)` down to its first match with `[:1]`. A path like `asset[*].id` legitimately matches several fields, so that dropped entities. I reverted that line, which fixed `test_find_entities_with_field_only`.

I haven't committed anything.