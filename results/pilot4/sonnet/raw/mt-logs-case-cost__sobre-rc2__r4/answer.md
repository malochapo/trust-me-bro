## Recap

**Cost inflation**
- **Cause:** commit `20f33137` (2025-09-02) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py`. Cost used to stop at the earliest of `stable_at`, `escalated_at` and `closed_at`. It now ran to the latest, so cases that were escalated or closed before being marked Stable accrued extra hours.
- **Deploy:** image `main-65f7df6e` rolled out on 2025-09-02 around 18:14–18:15 UTC. The scheduler that recalculates costs restarted on it at 18:15:24.
- **Evidence:** the finance sync flagged five jumps over 1,000, each on a Stable case. They are cases 5284 (Sep 3), 5327 (Sep 5), 5264 (Sep 8), 5363 (Sep 9) and 5406 (Sep 12). The first, on Sep 3 11:20 UTC, was 3,331 → 8,804. That is the earliest inflated sync in the logs and the basis for FIRST_INFLATED. I haven't checked whether those cases were also escalated or closed.
- **Fix:** I restored `min` and added `test_case_cost_stops_at_earliest_status_timestamp`. The test fails on the `max` version and passes now.

**Hourly TypeError (since 2025-09-08)**
- **Cause:** `get_hourly_rate` divides `project.annual_employee_cost` by `project.business_year_hours`. The error "unsupported operand type(s) for /: 'NoneType' and 'int'" means the left operand, `annual_employee_cost`, was `None`. The columns are nullable, and I couldn't tell from the repo or logs why those projects had no value.
- **Fix:** a missing annual cost now falls back to the `Project` model default (50000), and a missing or zero business year hours falls back to 2080. I added `test_get_hourly_rate__missing_project_settings`.
- **Not fixed:** `get_hourly_rate` in `src/dispatch/incident_cost/service.py` has the same bug.

All changes are uncommitted in the working tree. Costs already inflated since Sep 2 will correct at the scheduler's next recalculation after deploy, but the finance warehouse rows from that period need a reload.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost