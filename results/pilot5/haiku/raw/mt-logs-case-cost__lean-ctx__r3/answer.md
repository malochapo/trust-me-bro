Here's the recap for the incident report. The six lines at the end are the fields you asked for.

**Summary**

- **What happened:** Starting with the 09-02 deploy, stable cases had their response cost inflated, sometimes several times over. For example, case 5363 went from 2261 to 6241 on 09-09, and case 5264 went from 3285 to 11987 on 09-08. The cause was commit `20f33137`, which changed the cost cut-off from `min` to `max` over the stable, escalated and closed timestamps. Accrual then ran past the first status change and was billed up to the latest one. The function's own comment said "earliest relevant timestamp", so `min` was the intended behaviour.
- **Fix:** `src/dispatch/case_cost/service.py` now uses `min` again. A regression test, `test_case_cost_stops_at_first_status_change`, reproduces the over-billing (7200 s instead of 3600 s) and passes with the fix.
- **Second issue:** Since 09-08, the hourly job also logged a `TypeError` for some cases. The cause is a null `annual_employee_cost` or `business_year_hours` on the project. The job skipped those cases, so their costs went stale. `get_hourly_rate` now uses the model defaults (50000 and 2080) for whichever value is missing. Tests cover this.
- **Test results:** `python -m pytest` gives 362 passed, 4 skipped, and 8 failed. The 8 failures are in the AI, database and entity tests, and they fail on the original code too.

**Open items**

- The warehouse still has inflated values for the affected stable cases, so they need a recalculation.
- The incident-cost module has the same `get_hourly_rate` code and would hit the same `TypeError` for those projects. The logs show no such error from the incident job, so I haven't changed it.
- I haven't checked which projects have null settings, and I haven't confirmed the escalation timeline for 5363 against the database.
- Nothing is committed.
- The first inflated date is based on the diffs: 09-02 19:20 shows a normal-sized increase, and 09-03 11:20 (case 5284, 3331 → 8804) is the first clearly inflated value.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost