Recap for the incident report. Two things were fixed in `src/dispatch/case_cost/service.py`, and both are uncommitted in the working tree.

**1. Inflated case costs (the main bug)**
- Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, Sep 2) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cost cut-off became the latest of `escalated_at`, `stable_at`, and `closed_at` instead of the earliest. Cases that escalated before going Stable kept accruing participant time until the Stable transition.
- The fix restores `min`. Regression test: `test_case_cost_stops_at_earliest_stable_or_escalated_time`. It fails on the buggy line (7200s vs 3600s) and passes with the fix.
- It shipped in `main-65f7df6e`, which rolled out to `dispatch-web` on Sep 2 at 18:14 UTC (11:14 PT). The scheduler followed at 18:15 UTC. `main-51546e13` (Sep 4) also contains it.
- Earliest flagged inflated cost is case 5284 on Sep 3 at 11:20 UTC (3331 → 8804). I found no earlier Stable-transition jump after the deploy. The small increases on Sep 2–3 are new cases ramping up, not this bug.

**2. Hourly TypeError (separate)**
- The scheduler's 708 `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` errors come from `get_hourly_rate` in the same file, which divided `annual_employee_cost` by `business_year_hours` with no null check. Those projects had `annual_employee_cost` NULL (the numerator is the `None`).
- Fix: `get_hourly_rate` now falls back to `DEFAULT_ANNUAL_EMPLOYEE_COST` (50000) and `DEFAULT_BUSINESS_YEAR_HOURS` (2080). These constants now live in `src/dispatch/project/models.py` and back the model's column defaults and schema defaults. Regression tests: `test_get_hourly_rate_uses_project_defaults_when_unset` and `test_case_cost_with_unset_project_cost_fields`.
- I did not find which projects have these fields NULL, or how they got that way. The logs don't say, so the project table should be checked.

**Test status:** `tests/case_cost/test_case_cost_service.py` passes (22). The full suite has 362 passed, 4 skipped, and 8 failures in the AI service, one database test, and one entity test. Those 8 also fail on the unmodified tree.

**Open items:**
- `incident_cost/service.py` has the same `get_hourly_rate` with no null fallback. The scheduler log shows no errors from it, but it would fail the same way. I didn't change it.
- Finance's `case_response_cost` rows for affected cases still hold inflated values. They need recomputing after deploy.
- I haven't committed anything.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost