Recap for the incident report. The fixes are in the working tree and not committed.

**Incident recap**

- **Cost inflation:** Commit `20f33137` (Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min` to `max` in `get_participant_role_time_seconds`. The cut-off for a case's response time became its latest stable/escalated/closed timestamp instead of the earliest. Stable cases kept accruing participant time, so the classic cost rose several times over. It shipped in `dispatch:main-65f7df6e`, rolled out Sep 2 at 18:14 UTC. The first inflated case in the sync diffs is case 5284, which jumped from 3331 to 8804 at the Sep 3 11:20 UTC sync. The finance job's 1.5.0 rollout is not the cause; it only copies values from Dispatch.
- **Fix:** Restored `min` (`src/dispatch/case_cost/service.py`). Added `test_case_cost_cut_off_is_earliest_status_timestamp`, which fails with `max` and passes with `min`.
- **Hourly TypeError:** Projects can have a NULL `annual_employee_cost`. The project update path writes explicit nulls, and the column default only applies on insert. `get_hourly_rate` divided by it with no null check, so the case cost calculation raised a TypeError for those cases every hour. Since Sep 8 the scheduler has logged these failures, and the cases did not get a cost.
- **Second fix:** `get_hourly_rate` in both `case_cost` and `incident_cost` now falls back to `DEFAULT_ANNUAL_EMPLOYEE_COST` (50000) and `DEFAULT_BUSINESS_YEAR_HOURS` (2080) from `project/models.py`. Tests cover the fallback in both modules. Case, incident, and project suites pass: 44 tests.

**Open items**

- Stored values for affected cases still need correcting: the Dispatch values by re-running the recalculation, and the finance warehouse rows by backfill or re-sync.
- Projects with NULL values still exist. Rejecting `None` in `ProjectUpdate` would stop new nulls, but that changes the API.
- The logs don't name which project has the NULL. The `fraud` project appears often in the scheduler log, but I haven't tied it to the errors.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost