## Recap

**Cost inflation**
- **Cause:** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function sets the cut-off for how long each participant's role time is billed. With `max`, any non-new, non-triage case with a later `closed_at` or `escalated_at` keeps accruing role time after it went stable.
- **Deploy:** the first image containing it was `main-65f7df6e`, rolled out on 2025-09-02 at about 18:14–18:15Z. The 09-04 `main-51546e13` deploy only carried it forward.
- **Detection:** the finance job's first "flagged for review" warning was case 5284 on 2025-09-03 at 11:20Z (+164%). There was one before 09-09 for case 5363 ($2,261 → $6,241), plus 09-05 and 09-08.
- **Fix:** I reverted the line to `min`. The regression test `test_case_cost_stops_at_earliest_status_timestamp` fails without the fix.

**Hourly TypeError**
- **Cause:** `get_hourly_rate` divides `project.annual_employee_cost` by `project.business_year_hours`. The error was `NoneType / int`, so the missing value was the numerator, `annual_employee_cost`. A missing `business_year_hours` would crash the same line with a different message.
- **Fix:** it now falls back to the `Project` model default for whichever value is missing. The new tests are `test_get_hourly_rate__missing_project_settings_use_defaults` and `test_calculate_case_response_cost__project_without_cost_settings`.
- **Open question:** the logs don't show why it began on 2025-09-08. No deploy happened then, so a project setting was probably cleared. That is a guess.

**Caveats**
- **First inflated date:** the log contains only the 2025-09-03 flagged diffs. Smaller inflation of a Stable case could have been synced between the 09-02 deploy and that warning. I saw no such jumps, but the logs don't prove there weren't any.
- **Not shipped:** the fixes aren't committed or deployed. Costs for cases that went Stable since 2025-09-02 still need recomputing.
- **Not changed:** `incident_cost` has the same unguarded `get_hourly_rate`, which I left alone.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost