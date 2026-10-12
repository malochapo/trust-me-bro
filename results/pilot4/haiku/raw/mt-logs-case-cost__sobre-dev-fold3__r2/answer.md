## Recap

**Inflated case costs.** Since Sep 3, five Stable cases have been charged 2.5–3.7x their previous cost in a single hourly sync. The affected cases are 5284, 5327, 5264, 5363 and 5406. The cause is commit `20f33137` (Jordan Lee, Sep 2), which changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cost cut-off became the latest of `stable_at`, `escalated_at` and `closed_at` rather than the earliest, so a case escalated and later marked stable accrued cost up to the stable time. It shipped in the `main-65f7df6e` deploy, which rolled out Sep 2 at 18:14–18:15 UTC. The first affected sync was Sep 3 at 11:20 UTC. **Fixed:** the `min` is restored, and `tests/case_cost/test_case_cost_service.py` has a regression test that fails on the old code. I have not confirmed the case timestamps directly, since the logs don't contain them.

**Hourly TypeError.** Since Sep 8 at 15:55 UTC the cost job has logged 708 `TypeError`s. `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` with no check, so a NULL value raised. **Fixed:** missing values now fall back to the project model defaults (50,000 and 2,080), with tests. Cases in those projects are now costed at $25/hour, which finance should check against their real rates. I have not confirmed how the NULLs were written. The likely path is a project update that sends an explicit `null`. The same `get_hourly_rate` exists unchanged in `incident_cost/service.py`.

Neither fix is deployed yet, and the warehouse still holds the inflated values, so the affected cases need recalculating after deploy.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost