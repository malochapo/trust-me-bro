Here is the recap for the incident report. The six lines are at the end.

**Summary**

- **Symptom:** Since early September, the finance warehouse received case response costs several times higher than before. Case dispatch-default-security-5363 went from $2,261 to $6,241 on Sep 9, when it was marked Stable. Nobody changed the hourly rates or the cost models.
- **Root cause:** On Sep 2, commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function picks the cut-off for participant time from a case's `escalated_at`, `stable_at` and `closed_at`. The original `min` stops the clock at the first milestone. With `max`, a case that was escalated and then marked Stable kept accruing time until it was marked Stable. Finance was billed for the escalated-to-Stable window.
- **Deploy:** The image `registry.example.com/dispatch:main-65f7df6e` rolled out to `dispatch-web` and `dispatch-scheduler` on Sep 2 at 18:14–18:15 UTC. Commit `20f33137` is an ancestor of that build. The first inflated sync is Sep 3 at 11:20 UTC (case 5284, 3331 → 8804). There are no large jumps before the deploy. The image from Sep 4 (`main-51546e13`) does not touch the cost logic.
- **Why tests missed it:** The existing `test_case_cost_stops_at_stable_time` sets only `stable_at`, so `min` and `max` give the same result. No test covered a case with both `escalated_at` and `stable_at`.
- **Secondary bug:** From Sep 8, `case_cost.scheduled` logged a `TypeError` for a few cases every hour, 708 times in total. `get_hourly_rate` divided `project.annual_employee_cost` by `project.business_year_hours` without checking for NULL. The affected cases lost both their new and classic costs for those hours. The logs don't say which projects had the NULLs, and I didn't find what set them.

**Fixes (uncommitted, in the working tree)**

- `src/dispatch/case_cost/service.py`: `max` is back to `min`. `get_hourly_rate` falls back to the project defaults when either value is `None`.
- `src/dispatch/project/models.py`: the defaults (50000 and 2080) are now named constants, and the column defaults use them.
- `tests/case_cost/test_case_cost_service.py`: a regression test for escalation followed by Stable, and two tests for the unset-value fallback. I checked that the new tests fail when the fix is removed. The case_cost suite passes, 22 of 22.

**Caveats for the report**

- The fixes are not deployed. Costs already synced since Sep 2 remain wrong until the warehouse rows are backfilled.
- `FIRST_INFLATED` is based on hourly jumps over 300. A smaller inflation on the evening of Sep 2 can't be ruled out from these logs.
- `incident_cost/service.py` has the same `get_hourly_rate` without the fallback. The logs show no errors from it.
- Zero values for `business_year_hours` still raise `ZeroDivisionError`. The logs showed only NULLs, so I didn't guard that case.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```