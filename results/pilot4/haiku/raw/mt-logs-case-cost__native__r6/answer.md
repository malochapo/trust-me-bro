The recap is below. `FIRST_INFLATED` is based on the first large increase in the sync log. I did not verify that against case records.

## Recap

**Cost inflation.** Since Sep 2, some case response costs have been several times what they should be. Each case was charged for time up to its Stable time rather than its earlier escalation time. Commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off", changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py`). The function's own comment said "earliest", and the `min` dates to `200cd428` (Jun 24, "adds stable status to cases"). The change reached production in image `main-65f7df6e`, which rolled out on Sep 2 at 18:14–18:15 UTC. The first large inflated case in the sync log is case 5284 on Sep 3 at 11:20 (3331 → 8804). The example case, 5363, jumped from 2261 to 6241 on Sep 9. **Fix:** restored `min`. **Regression test:** `test_get_participant_role_time_seconds_stops_at_earliest_cutoff`. It gives 7200 s on `max` and 3600 s on `min`.

**Hourly TypeError.** Since Sep 8, the hourly job has failed on some cases with `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` (708 occurrences). `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. Projects with a NULL `annual_employee_cost` make the division fail, so those cases get no cost update. The model's column default only applies on insert, so existing NULL rows keep their NULL. **Fix:** the project model defaults are now named constants (50000 and 2080), and `get_hourly_rate` falls back to them for any NULL value. **Tests:** `test_get_hourly_rate_uses_project_defaults_for_missing_values` and `test_calculate_case_response_cost_classic_with_unset_project_costs`. Both fail on the original code.

**Test suite.** 362 passed, 4 skipped, 8 failed. The failures predate these changes: six AI tests need a tokenizer download the sandbox can't reach, and two database and entity tests also fail on the unmodified commit.

**Open items:**
- `src/dispatch/incident_cost/service.py:131` has the same unguarded division, so incident cost likely fails the same way for projects with NULL fields. I did not change it.
- Some cases dropped sharply after the Sep 2 deploy (case 5291 at 19:20, case 5322 at 01:20 on Sep 3). The bug can only raise costs, so these drops are unexplained.
- Nothing is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost