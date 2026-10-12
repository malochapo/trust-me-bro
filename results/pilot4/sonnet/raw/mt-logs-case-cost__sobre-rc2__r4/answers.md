I've traced it to one commit. I haven't changed any code.

**Root cause**

`20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, 2025-09-02), changed `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py` from `min(timestamps)` to `max(timestamps)`.

- **What the code does:** The timestamps are `stable_at`, `escalated_at` and `closed_at`. They set the point where a participant's role time stops counting. The comment above the block still says "earliest relevant timestamp", so the code now contradicts it.
- **Effect:** Cost used to stop at the first of those events. It now keeps accruing until the last one.
- **Case 5363:** I did not check its timestamps. It fits the pattern if it was escalated before it went Stable. The cut-off then moved from `escalated_at` to `stable_at`, which would explain $2,261 → $6,241 when it was marked Stable on Sep 9.
- **Why the warehouse is affected:** The scheduler's `calculate_cases_response_cost` job recalculates costs every 4 hours. `case-cost-sync` (1.4.2 for the whole log window) only copies what Dispatch's API returns, so the finance job is not at fault.
- **Why Stable cases:** The sync flagged five jumps on Sep 3, 5, 8, 9 and 12. All five of the flagged jumps I looked at were on Stable cases, with increases of +147% to +265%. Examples are case 5284 (3331 → 8804) and case 5264 (3285 → 11987). I did not check whether those cases were also escalated or closed.

**The deploy that shipped it**

Deploy `main-65f7df6e`, on 2025-09-02 at about 18:14–18:15 UTC. It includes `20f33137`, since that commit sits two commits before `65f7df6e` in history.

- **Db-upgrade job:** `dispatch-db-upgrade-65f7df6e` pulled `registry.example.com/dispatch:main-65f7df6e` at 18:14:09.
- **Scheduler:** The old scheduler pod was killed at 18:14:41, and the new scheduler pod started at 18:15:24.
- **Why it isn't the previous deploy:** The previous image, `main-3e0445ff` (2025-08-27), predates the commit.
- **Later deploy:** `main-51546e13` (2025-09-04) also contains the change, but it was not the first to ship it.

**Suggested fix, not applied**

Revert `max` back to `min`. If the intent was to keep counting until close, make that an explicit, reviewed change. After the fix, costs for already-affected cases will need recomputing, and the finance team should be told that the warehouse values since Sep 2 are inflated.

----- next turn -----

The fix and a regression test are in the working tree. I haven't committed anything.

- **Fix:** In `src/dispatch/case_cost/service.py`, `get_participant_role_time_seconds` is back to `min(timestamps)`, so cost stops at the earliest of `stable_at`, `escalated_at` and `closed_at`.
- **Test:** I added `test_case_cost_stops_at_earliest_status_timestamp` to `tests/case_cost/test_case_cost_service.py`.
  - **Case 1:** It sets up a closed case with escalated, stable and closed timestamps, and expects cost to stop at `escalated_at`.
  - **Case 2:** With `escalated_at` cleared, it expects cost to stop at `stable_at` rather than `closed_at`.
  - **Gap:** The existing test only ever set one timestamp, so `min` and `max` gave the same answer and the bug went unnoticed.
- **Results:** All 20 tests in `tests/case_cost` pass with the fix. With the fix stashed (the `max` version), the new test fails.

Costs already recalculated since Sep 2 will correct themselves at the next scheduler run (every 4 hours) once this is deployed. The finance team should still reload or ignore the inflated warehouse rows from Sep 2 onward.

----- next turn -----

The TypeError is fixed. Cases in projects with no cost settings now get a cost from the project model's defaults. The fix and the test are in the working tree, uncommitted.

**Cause**

- **The failing line:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `project.annual_employee_cost / project.business_year_hours`. When one of those is `None`, it raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`.
- **How the scheduler hits it:** The traceback in `scheduler.log` runs from `calculate_cases_response_cost` through `update_case_response_cost` and `calculate_case_response_cost_new` into `get_hourly_rate`. It repeats every hour at :55 from 2025-09-08 15:55.
- **Why those cases get no cost:** The scheduler catches the error per case. The affected cases just never get a cost written, and the job logs the error each hour.
- **Why the values are `None`:** Both columns are nullable, and the project update schema accepts `None`. I couldn't tell from the repo or logs how or why those projects ended up with unset values.

**Fix**

- When `annual_employee_cost` is `None`, `get_hourly_rate` now uses the `Project` model's column default (50000).
- When `business_year_hours` is `None` or 0, it uses the model default (2080). Treating 0 as missing also avoids a ZeroDivisionError.
- The defaults are read from the `Project` model, so there's a single source of truth.

**Test**

`test_get_hourly_rate__missing_project_settings` in `tests/case_cost/test_case_cost_service.py` covers both values set, each one missing, and both missing. It fails on the old code. `tests/case_cost` and `tests/incident_cost` pass (36 tests).

`src/dispatch/incident_cost/service.py` has an identical `get_hourly_rate` with the same bug. I left it alone since you only asked about cases, but the same fix would apply there.

----- next turn -----

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