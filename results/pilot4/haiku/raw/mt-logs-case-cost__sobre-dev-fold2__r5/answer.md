The flagged jump on case 5284 at the Sep 3 11:20 sync is the first clear inflation from a stable transition. Cases 5346 and 5349 were newly added cases accruing normally, so they don't count. Here is the recap.

**Recap**

- **Symptom:** After September 2, the finance warehouse received case response costs several times the previous hour's values for cases that had just been marked stable. Example: `dispatch-default-security-5363` went from $2,261 to $6,241 on Sep 9.
- **Root cause:** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function is meant to stop billing a participant's role at the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, billing ran until the latest of them, so an escalated-then-stable case was billed for the whole escalated-to-stable window. The existing tests set only `stable_at`, so `min` and `max` gave the same result and the regression went unnoticed.
- **Deploy:** The `dispatch:main-65f7df6e` image rolled out on 2025-09-02 at 18:14 UTC, and it contains `20f33137`. The earlier image, `main-3e0445ff`, does not.
- **Fix:** `min` is restored, with a regression test that fails on `max` (3600 s expected, 10800 s returned). Separately, `get_hourly_rate` now falls back to the project model's defaults when `annual_employee_cost` or `business_year_hours` is NULL. That removes the scheduler `TypeError` from Sep 8 onward. A test covers it.
- **Open items:** Restate the warehouse rows affected since the Sep 2 deploy. Find out which projects have NULL settings. Consider the same guard for `incident_cost/service.py:131`.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost