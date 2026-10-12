I have what I need. Recap of the incident:

**Cost bug (`case_cost`):** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cost cut-off became the latest of `escalated_at`, `stable_at` and `closed_at`, not the earliest, which the function's comment says it should be. Any case with more than one of these timestamps was billed too long, and those cases showed jumps of 2.5–3.7×. The commit reached production in `main-65f7df6e`, rolled out on Sep 2 at 18:14Z. The first inflated case I found is case 5284 on Sep 3 at 11:20Z. The cost-sync job only flags Stable cases, so an escalated or closed case inflated earlier would not show up in the warnings. I checked the classic-cost diffs since the deploy for jumps above 1.5× on cases with a base over 500, and found no earlier ones.

**Hourly TypeError (`scheduler`):** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` without checking for `None`. The log error reads `'NoneType' and 'int'`, so the missing value is `annual_employee_cost`. Those cases were skipped every hour. The fix uses the `Project` column defaults when either value is missing.

**Fixes and tests:** The `min` fix has a regression test that fails on the old code. The hourly-rate fallback has four tests, three of which fail on the old code. The case cost suite passes: 24 tests.

**Not fixed:** `src/dispatch/incident_cost/service.py:133` has the same unguarded `get_hourly_rate`. The `max` bug in the case cost code is not in the incident cost code, which I did not check in depth.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```