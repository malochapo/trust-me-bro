The test suite is green: 351 passed, 4 skipped, with `tests/ai/test_ai_service.py` excluded as you asked. I changed two source files and no tests.

**Code fixes** (both were regressions from this week's commits):

- **`src/dispatch/entity/service.py`**: commit `beb60cc4` added `[:1]` to the JSONPath matches, so wildcard paths like `asset[*].id` only ever produced the first entity. I removed the slice so all matches are returned again.
- **`src/dispatch/database/service.py`**: commit `42699ebc` flattened `restricted_case_filter` and dropped the `and_(...)` around the restricted-case check. Members then saw every restricted case, not just the ones they participate in. I restored the grouping so it matches `restricted_incident_filter`.

**Environment issue (not a code change):** every DB test errored at setup. The shell sets `DATABASE_PORT=5433`, and that cluster's `template1` is `SQL_ASCII`, so `CREATE DATABASE` fails. The UTF8 cluster on 5432 works. I ran the suite with `DATABASE_PORT=5432` for those runs only and did not change your shell profile or the test config. If you want `python -m pytest` to work without the override, either point `DATABASE_PORT` at 5432 or recreate the 5433 cluster with a UTF8 template.

Nothing is committed.