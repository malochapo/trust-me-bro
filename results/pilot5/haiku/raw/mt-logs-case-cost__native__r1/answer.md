Here's the recap for the incident report. The six lines are at the end.

**Incident recap: inflated case response costs and missing-setting TypeError**

**1. Inflated costs.** Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min` to `max` when picking the cost cut-off in `get_participant_role_time_seconds`. The cut-off became the latest of `escalated_at`, `stable_at` and `closed_at` instead of the earliest. Participant time therefore kept accruing after a case was marked stable. Cases were overstated from the moment they were marked stable, for example case 5363 went from 2261 to 6241 on 2025-09-09. The commit shipped in `main-65f7df6e`, rolled out to `dispatch-web` and `dispatch-scheduler` on 2025-09-02 at 18:14–18:15 UTC. The first large jump in the cost-sync log is on 2025-09-03 (case 5284), and the later flagged cases are 5327, 5264, 5363 and 5406.
- Fix: restored `min`. Regression test `test_get_participant_role_time_seconds_stops_at_first_milestone` fails on the old code and passes now.
- Not done: the finance warehouse rows already written with inflated values are not corrected. The next hourly sync recomputes them from the fixed code, but the flagged cases were overstated from 2025-09-02 18:15 until then.

**2. Hourly TypeError.** Since 2025-09-08 15:55, the scheduler's `calculate_cases_response_cost` job logged `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` 708 times. The job calls `get_hourly_rate`, which divides `annual_employee_cost` by `business_year_hours`. Some projects have no `annual_employee_cost`, so those cases were skipped and got no cost.
- Fix: a missing `annual_employee_cost` or `business_year_hours` now falls back to the Project model defaults, 50000 and 2080. Two regression tests cover this; both fail without the fix.
- Not done: `src/dispatch/incident_cost/service.py:133` has the same unguarded division for incidents. I did not change it, because it's outside the case cost job.

**3. Process.** The full suite has 8 failures in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. They also fail on the original code, so they predate these changes. I did not commit any of the changes.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost