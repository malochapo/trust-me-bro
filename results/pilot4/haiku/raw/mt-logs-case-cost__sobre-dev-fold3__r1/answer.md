## Recap

**Cost inflation:** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. For cases past the new/triage stage, the cost cut-off moved from the earliest of escalated, stable and closed to the latest. Each participant's time in role therefore ran until the last of those timestamps, which inflated the case response cost. The commit reached production in image `main-65f7df6e`, which rolled out on 2025-09-02 at about 18:14 UTC. The scheduler restart at 18:15:30 confirms the rollout. The first flagged inflated Stable case in the logs is 2025-09-03; the log has no earlier flags, so the first inflated cost may be a few hours before that. I did not verify it against the case rows.

**Fix:** I reverted the line to `min(timestamps)`. A regression test in `tests/case_cost/test_case_cost_service.py` fails on the broken code and passes with the fix.

**TypeError:** The hourly job raised `unsupported operand type(s) for /: 'NoneType' and 'int'` from `get_hourly_rate`, because `annual_employee_cost` was NULL on some projects. Those cases got no cost. I made `get_hourly_rate` fall back to the project model defaults (50000 and 2080) when a value is `None`. I moved those defaults into named constants in `src/dispatch/project/models.py`, and the column defaults and schema use the same constants. Two new tests cover the fallback.

**Test results:** `tests/case_cost` passes (22 tests). The full suite has 362 passing and 8 failing. The 8 failures are in `tests/ai`, one database filter test and one entity test. They also fail without my changes, so they predate this work.

**Open items:**
- `src/dispatch/incident_cost/service.py` has the same unguarded division, so incident costs will fail the same way on projects with NULL values. I did not change it.
- A `business_year_hours` of `0` still raises `ZeroDivisionError`. Nothing in the logs shows that case.
- The affected projects are not named in the logs, and the database rows are unchanged. Finance will need a backfill for inflated cases.
- Nothing is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost