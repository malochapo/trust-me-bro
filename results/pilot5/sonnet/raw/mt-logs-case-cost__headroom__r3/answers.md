The cause is commit `20f33137`, which went to production in the 2025-09-02 deploy of image `main-65f7df6e`. I confirmed the code change and the deploy timing. The exact trigger for the later recalculation is an inference, because the logs don't include per-case status history.

**Root cause**
- `20f33137` is "fix(case_cost): use the latest status timestamp as the cost cut-off", by Jordan Lee, committed 2025-09-02 09:29 PDT (16:29 UTC).
- It changed one line in `get_participant_role_time_seconds()` (`src/dispatch/case_cost/service.py:353`): `min(timestamps)` became `max(timestamps)`.
- The timestamps are `stable_at`, `escalated_at` and `closed_at`. The cost clock now stops at the latest of them instead of the earliest. The comment above it still says "earliest relevant timestamp". The commit message says "latest" and the code agrees, but the surrounding logic assumes the earliest.
- The cut-off only applies to cases that aren't `new` or `triage`. A case that is stable and has other status timestamps now accrues cost up to the latest one.
- No rates or cost models changed. Case 5363 grew by about $146 an hour before and after.
- `calculate_cases_response_cost` (`src/dispatch/case_cost/scheduled.py`) recalculates a stable case only if its cost was last updated at or before `stable_at`. So a stable case's cost stays frozen at the value from the old code, then is recomputed once with the new code when `stable_at` is set again.
- That matches your example. Case 5363's classic cost stayed at $2,261 from 09-05 16:20 until 09-09 12:20 UTC, then jumped to $6,241.

**Evidence in the logs**
- case-cost-sync flagged a spike only five times in the 3 weeks, and every flagged case is Stable. These are the only `costsync.checks` warnings in the file:

| Case | Flagged at (UTC) | Change |
|---|---|---|
| 5284 | 09-03 | 3,331 → 8,804 |
| 5327 | 09-05 | 2,244 → 5,539 |
| 5264 | 09-08 | 3,285 → 11,987 |
| 5363 | 09-09 | 2,261 → 6,241 |
| 5406 | 09-12 | 1,975 → 4,945 |

- There were no flags before the deploy, and the first one came about 17 hours after it.
- Cases 5284 and 5327 show the same pattern as 5363. Each has a frozen value, then one large jump days later.

**The deploy**
- The change was never in production before 09-02, so the 08-27 image `main-3e0445ff` (committed 08-26) predates it. `20f33137` is the first commit in the 09-02 batch of merges.
- `dispatch-db-upgrade-65f7df6e` started pulling `registry.example.com/dispatch:main-65f7df6e` at 2025-09-02 18:14:09 UTC.
- The scheduler pod `dispatch-scheduler-qdd74fpnsl` started on that image at 18:15:24 UTC.
- `65f7df6e` was committed after `20f33137`, so the image includes it.
- `main-51546e13` (the 09-04 16:52 deploy) also contains it, but it is not where the bug first shipped.

**Ruled out**
- Finance's `case-cost-sync` moved from 1.4.2 to 1.5.0 on 09-01, a day before the deploy. It only copies what the API returns, and the first flag came after the Dispatch deploy.
- The Postgres connection refusals on 09-06 at 03:54 and the `annual_employee_cost` None errors that start 09-08 at 15:55 are separate problems. They break the new cost model, not the classic one. They didn't cause these jumps.

**What I'd do next** (not done, per your instruction)
- Revert `20f33137`, or make the cut-off `min` again.
- Recompute the costs of stable, escalated and closed cases since 09-02 18:14 UTC.
- Have finance re-sync the warehouse rows that changed after that time.

I haven't confirmed the intent behind `20f33137`. If it fixed a real problem, such as a reopened case with a stale `closed_at`, that needs a different fix.

----- next turn -----

I reverted the regression: the cost cut-off in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py`) is `min(timestamps)` again. All 20 tests in `tests/case_cost` pass. I did not run the rest of the suite and nothing is committed.

I added `test_case_cost_stops_at_earliest_status_timestamp` to `tests/case_cost/test_case_cost_service.py`. It sets `stable_at` 6 hours after the participant started, with later `escalated_at` and `closed_at` values. It asserts the cost stops at `stable_at`.

I also ran the new test against the old `max` code, and it fails there. It calculates 32,400 seconds against the 14,400 expected, which is the inflation you saw.

The existing `test_case_cost_stops_at_stable_time` only set `stable_at`, so `min` and `max` gave the same answer. That is why the change went through unnoticed.

This does not repair the bad numbers already in the warehouse. Cases recalculated since the 2025-09-02 18:14 UTC deploy hold inflated costs. The scheduler only recomputes stable cases when `stable_at` moves past the last cost update. Those costs need a one-off recalculation, and finance needs to re-sync the affected rows. I haven't done either.

I still don't know why `20f33137` was written. If it was meant to fix a case with a stale `closed_at` or `escalated_at`, that problem is now back and needs its own fix. Jordan Lee, who made the change, could tell you.

----- next turn -----

Status: the work is done and tests pass. Here is the summary.

**Cause of the TypeError**
- `get_hourly_rate()` in `src/dispatch/case_cost/service.py` divided `project.annual_employee_cost` by `project.business_year_hours`. For some project, one of the two was NULL, so the division raised `TypeError`.
- The scheduler log shows the `fraud` project first appearing at 2025-09-08 14:54. The first error came at 15:55, the first hourly run after it. That timing is why I think `fraud` is the project involved. The logs don't name the project in the error, so this is an inference.
- Both columns are nullable. `ProjectBase` allows `None`, and `project_service.create` passes the values straight through. A project created with an explicit `null` for either field stores NULL, and the column default never applies.
- The `calculate_cases_response_cost` job catches exceptions per case. That's why the job kept running and logged one error per failing case. Those cases got no classic or new cost at all, because the new-model calculation runs first and fails.

**Fix**
- `get_hourly_rate()` now uses the project model's column defaults when a value is NULL: 50,000 for annual cost and 2,080 for business year hours. It checks `is None`, so an explicit 0 is not replaced.
- I added `test_get_hourly_rate_uses_project_defaults_for_unset_values` in `tests/case_cost/test_case_cost_service.py`. It covers both values set, each one missing, and both missing. It fails on the old code.
- `tests/case_cost`, `tests/project` and `tests/incident_cost` pass together (42 tests). The earlier `min` fix is still in the same working tree. Nothing is committed.

**Related, not changed**
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division. I left it alone because you asked about cases. A NULL project would fail the same way for incidents.
- The `fraud` project still has NULLs in the database. The fix works around them when computing cost. If you want the data cleaned up, or `project_service.create` to apply the defaults, that's a separate change.
- Cases in that project that failed since 09-08 will get a cost on the next hourly run, since they were never saved.

----- next turn -----

Case costs were inflated by a one-line regression in the case cost calculation. It shipped in the 2025-09-02 deploy of `main-65f7df6e`. The first inflated cost reached the warehouse on 2025-09-03.

**Cost bug**
- Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`, in `src/dispatch/case_cost/service.py`.
- That is the cut-off after which a case stops accruing cost. It is taken from the case's `stable_at`, `escalated_at` and `closed_at` timestamps. With `max`, a case that is stable and also has later status timestamps kept accruing cost up to the latest one.
- Stable cases are only recalculated when `stable_at` moves past the last cost update. A stable case therefore stays frozen at a correct value, then jumps once when it is recalculated with the bad code.
- The fix is in the working tree, uncommitted: `min` is back, with a regression test.

**Timeline (UTC)**
- 2025-09-02 16:29: `20f33137` committed.
- 2025-09-02 18:14: db-upgrade pod for `main-65f7df6e` starts, and the scheduler follows at 18:15. This is the deploy that shipped the bug.
- 2025-09-03 11:20: first inflated cost in the warehouse feed. Case 5284 went from 3,331 to 8,804.
- Four more large jumps followed: case 5327 on 09-05, 5264 on 09-08, 5363 on 09-09 (2,261 to 6,241) and 5406 on 09-12. All five cases were Stable.

**Limits of the first-inflated date**
- I dated it from the largest upward jumps in `cost-sync.log`, which carries no per-case status or timestamps.
- A smaller inflation on 2025-09-02 or 2025-09-03 would not stand out in that data. 2025-09-03 is the earliest one visible.
- Compare the warehouse against a recalculation from Dispatch's own data to be sure.

**Cleanup still owed**
- Costs recalculated since 09-02 18:14 UTC are still wrong in Dispatch and in the warehouse. They need a one-off recalculation and a re-sync by finance.
- The history is ambiguous on whether `20f33137` was meant to fix a stale `closed_at` or `escalated_at` on reopened cases. If so, that problem is back and needs its own fix.

**Separate hourly TypeError (since 2025-09-08 15:55)**
- It is unrelated to the inflation, and not caused by the `max` regression.
- `get_hourly_rate()` divided `project.annual_employee_cost` by `project.business_year_hours`, and one of the two was NULL on a project.
- I believe the project is `fraud`, which first appears in the scheduler log on 09-08 at 14:54. The error itself doesn't name the project.
- `get_hourly_rate()` now falls back to the project model defaults when either value is NULL, with a test that fails on the old code.
- The incident cost code has the same unguarded division at `src/dispatch/incident_cost/service.py:133`. I left it alone.
- I picked `annual_employee_cost` for the report line below. The log doesn't say which of the two was NULL, and the fix handles both.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost