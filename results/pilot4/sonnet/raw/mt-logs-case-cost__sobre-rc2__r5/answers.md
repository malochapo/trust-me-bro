**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025‑09‑02) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`, at `src/dispatch/case_cost/service.py:353`.

**What the code does.** The function works out how long each participant spent in a role. A case that has left new/triage is billed only up to a cut-off. The cut-off is meant to be the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max()` it becomes the latest of them. The participant's own `renounced_at` is still applied, but only when it is earlier than that cut-off.

**Effect.** For any case with more than one of those timestamps, the cost window gets longer. For participants who never renounced the role, it runs until the latest timestamp (for example, closed or escalated after stable) instead of the stable time. Cases that are stable but have `escalated_at` or `closed_at` set later therefore jump in cost. Cases with only one timestamp don't change.

Dispatch's own numbers are wrong, so the finance warehouse is just copying bad data. `case-cost-sync` flags the jumps as cost increases, but only a few cases show up, so this is a gradual change on certain cases rather than a global one.

**Deploy that shipped it.** `main-65f7df6e`, rolled out to production on 2025‑09‑02 at about 18:14–18:15Z.
- `65f7df6e` is the first deploy after `20f33137`. It sits two commits later, with `5670487c` and `beb60cc4` in between.
- The `dispatch-db-upgrade-65f7df6e` job started at 18:14:26Z.
- The web replica set `dispatch-web-zrhzjwmzrh` replaced the old one by 18:15:54Z.
- The scheduler `dispatch-scheduler-qdd74fpnsl` came up at 18:15:09Z.
- The prior deploy, `main-3e0445ff` (2025‑08‑27), does not contain the commit.

**Evidence from the logs.**
- Every `case-cost-sync` run from 08‑25 until the deploy shows `0 flagged`.
- The first flagged jump is at 2025‑09‑03T11:20Z, in the first run after the cost recalculation on the new code, for case 5284 (`3331 → 8804`, +164%, Stable).
- The case in your example, 5363, shows `2261 → 6241` at 2025‑09‑09T12:20Z.

**Not the cause.**
- `main-51546e13` (09‑04) also contains the bug, but it is not where the bug was introduced.
- The 09‑10 scheduler pod restart reused the same `51546e13` image.
- The cost-sync job stayed on `case-cost-sync:1.4.2` throughout, so the finance job didn't change.

**Caveats.**
- I didn't run the cost calculation to reproduce the numbers.
- I didn't check why 5363 only jumped on 09‑09 when the deploy was 09‑02. Most likely its cost was recalculated or its status changed then.
- The logs only show the flagged cases, not how many were affected overall.

**Follow-up (no code changed).**
- Revert `min` → `max`.
- Recalculate the cost of every case that was non-new/triage and had two or more of `stable_at`, `escalated_at` and `closed_at` since 09‑02.
- Tell finance to overwrite the warehouse rows from that period.

The commit message describes the intent as a "latest" cut-off. If that was deliberate, the product decision conflicts with the comment ("earliest relevant timestamp") and the `renounced_at` comparison below it.

----- next turn -----

I reverted the bug in `src/dispatch/case_cost/service.py:353`, so the cut-off is `min(timestamps)` again, and added a regression test. All 20 tests in `tests/case_cost` pass with the fix.

The new test is `test_participant_role_time_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. It builds a closed case with `stable_at`, `escalated_at` and `closed_at` set at different times, and a participant role that never renounced. It expects the role time to stop at `stable_at`. I stashed the fix and re-ran, and the test fails with the `max()` code (it gets about an hour too much), so it would have caught the bug.

I haven't committed anything, and nothing is deployed yet. The fix still has to ship to production, and the affected cases need recalculating. After that, finance has to overwrite the warehouse rows from 2025‑09‑02 onward.

----- next turn -----

The TypeError is fixed and has a test. All 21 tests in `tests/case_cost` pass, and with the `src` change stashed the new test fails (alongside the earlier min/max one, which was stashed too).

**Cause.** `get_hourly_rate()` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Both columns are nullable, so a project with either one set to NULL raises `unsupported operand type(s) for /: 'NoneType' and 'int'`. The traceback in `scheduler.log` runs `calculate_cases_response_cost` → `update_case_response_cost` → `calculate_case_response_cost_new` → `get_hourly_rate`. It repeats 708 times from 2025‑09‑08 15:55.

The division code dates back to the original case-cost commit (`2b0bfcd7`), so the code didn't change on September 8. I think the trigger is data: cases from projects with NULL values started going through this path. I couldn't confirm that from the logs, because they don't name the projects.

**Fix.** `get_hourly_rate()` now uses the `Project` model's column default for whichever value is missing: 50000 for annual employee cost and 2080 for business year hours. It treats a missing business year hours as 0 or NULL, which also avoids a division by zero. I read the defaults from the model rather than hard-coding them.

**Test.** `test_get_hourly_rate_uses_project_defaults_for_missing_values` covers both values missing, only the cost set, and only the hours set.

- **Incident costs:** `incident_cost/service.py:131` has an identical `get_hourly_rate()` with the same flaw. I left it alone because you asked about case costs. Say if you want it fixed too.
- **Skipped cases:** the error handler in the scheduler skips the failing case, so those cases have had no cost recorded since 09‑08. They will pick one up on the next hourly run after this ships.
- **Not committed:** nothing is committed, and the changes are still uncommitted alongside the earlier min/max fix.

----- next turn -----

Checking the last details for the recap: the cost-sync version history and the first inflated case in the data.

**Recap**

1. **Cost inflation.** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in the case-cost cut-off. Cases with more than one of `stable_at`, `escalated_at` and `closed_at` were billed up to the latest one instead of the earliest. The commit is on `main`, and `65f7df6e` is the first image built after it. That image went to production on 2025‑09‑02 at about 18:14Z.
2. **Evidence.** The cost-sync job flagged no case before 2025‑09‑03T11:20Z. Its first jump is case 5284 (3331 → 8804). I scanned every sync diff from 09‑02 16:00Z to 09‑03 12:00Z for a rise of more than 400, and 5284 was the only one. Four more cases were flagged later: 5327, 5264, 5363 and 5406. Smaller inflations may not have been flagged, so treat 2025‑09‑03 as the first inflated case that shows up in these logs.
3. **Correction to my first answer.** I said the finance job stayed on `case-cost-sync:1.4.2` throughout. That was wrong. It moved to 1.5.0 on 2025‑09‑01 (first 1.5.0 run at 10:20Z). That is still before the bug shipped, and the 1.5.0 runs before 09‑02 flagged nothing. So I don't see the version change as a cause, but it should be in the report as a change in the same period.
4. **TypeError.** `get_hourly_rate()` divided a NULL `annual_employee_cost` (the traceback's `NoneType / int`) because the project columns are nullable. The code is old, so I think a data change triggered it, and the logs can't confirm that. It occurs 708 times from 2025‑09‑08 15:55. A NULL `business_year_hours` would be a separate failure with the operands reversed. Both are now defaulted.
5. **State of the fixes.** Both fixes and their tests are written and passing, but they are uncommitted and not deployed. Finance still needs to overwrite the warehouse rows from 09‑02 onward.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost