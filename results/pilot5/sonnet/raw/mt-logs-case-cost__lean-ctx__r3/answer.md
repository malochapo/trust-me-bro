## Recap

**Cost inflation**
- **Cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`. Billing used to stop at the earliest of `stable_at`, `escalated_at` and `closed_at`. It now ran to the latest, so a case that went stable and was later escalated or closed got billed for the gap.
- **Deploy:** the change went to production in image `dispatch:main-65f7df6e`, rolled out on 2025-09-02 at about 18:14–18:16Z. That covered the db-upgrade job, the scheduler and web. The later `51546e13` deploy on 09-04 contains the bug but didn't introduce it.
- **First inflated case:** case 5284 jumped from 3331 to 8804 in the 2025-09-03 11:20Z sync. Five cases show jumps of more than 400 in the logs (09-03, 09-05, 09-08, 09-09, 09-12). Case 5284 is the earliest. I can't rule out smaller inflations earlier than that.
- **Fix:** reverted to `min`, with a regression test (`test_case_cost_stops_at_earliest_status_timestamp`).
- **Still to do:** the warehouse needs a re-sync for affected cases.

**Hourly TypeError (separate bug)**
- **Cause:** `get_hourly_rate()` divided `project.annual_employee_cost` by `project.business_year_hours`. A project with either value NULL raised a TypeError. The column defaults only apply on insert.
- **When:** the errors start 2025-09-08 15:55:01 in `scheduler.log`, and there are 708 through 09-14.
- **Fix:** a NULL value now falls back to the `Project` column default, with a test (`test_get_hourly_rate_uses_project_defaults_for_unset_values`).
- **Unconfirmed:** the logs don't show why those projects have NULLs.
- **Not fixed:** `incident_cost/service.py:131` has the same unguarded division, and 0 business year hours would still divide by zero.

Both fixes are uncommitted in the working tree.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost