## Recap

**Cost inflation**
- Cause: commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`. This is the cut-off for when a participant's time stops counting. It should be the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, a case that has more than one of these timestamps was costed up to the latest one.
- Deploy: the commit shipped with image `main-65f7df6e`. Its db-upgrade job started on 2025-09-02 at 18:14Z, and the scheduler and web rollouts finished by 18:15:54Z. The 09-04 deploy (`main-51546e13`) only carried it forward.
- First inflation: the first large jump in the cost-sync log is case 5284 on 2025-09-03 at 11:20Z, from 3331 to 8804. I scanned every sync between the deploy and that run and found no other jump above 300. Cost-sync 1.5.0 (2025-09-01) is not involved.
- Fix: `max` is reverted to `min`, with a regression test.
- Still to do: recompute the case costs updated since 2025-09-02 18:15Z, and correct the matching warehouse rows.

**Hourly TypeError**
- Cause: `get_hourly_rate()` computes `annual_employee_cost / business_year_hours`. The error text is `NoneType / int`, so the numerator was None, which means `annual_employee_cost` was NULL on at least one project. The earlier "and/or" in my last message was looser than the evidence allows. A NULL `business_year_hours` would also fail, but with a different message, and the logs show none.
- The columns are nullable and the API accepts `None`. The column default only applies when no value is given at insert, so an explicit `None` is stored as NULL.
- Fix: both settings now fall back to the Project model's defaults, with tests.
- Not found: why it started on 2025-09-08, and which project it is.
- Not fixed: `incident_cost/service.py` has the same weakness, and nothing stops the API from writing NULLs again.

Nothing is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost