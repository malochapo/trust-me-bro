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