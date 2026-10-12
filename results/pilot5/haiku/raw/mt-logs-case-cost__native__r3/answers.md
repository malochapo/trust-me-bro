**Root cause:** commit `20f33137` changed one `min(...)` to `max(...)` in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`). The cost cut-off for a case is now its *latest* of stable/escalated/closed timestamps, not the earliest. For a case that was escalated and later marked stable, the cut-off jumps from the escalation time to the stable time, and the cost jumps with it.

**The deploy:** `main-65f7df6e`, rolled out to `dispatch-scheduler` on **2025-09-02 at 18:14–18:15 UTC** (`events.log`). `20f33137` is an ancestor of `65f7df6e`, so it shipped there. It was carried forward by `main-51546e13` on Sept 4 and again on Sept 10 restart. Scheduler logs show the restart at 18:15:30 that day. Note that `65f7df6e` is also dated Sept 2 and its commit timestamp is 09:40 PT, so the rollout is the first point where it reached production.

**Evidence from `cost-sync.log`:** the pattern is the same for every case that jumped, and each one was escalated before it was marked stable:

| Case | Cost flat from | Stable jump |
|---|---|---|
| 5284 | Aug 29 13:20 (3331) | Sep 3 11:20 → 8804 |
| 5327 | Sep 2 11:20 (2244) | Sep 5 16:20 → 5539 |
| 5264 | Aug 29 16:20 (3285) | Sep 8 10:20 → 11987 |
| 5363 | Sep 5 16:20 (2261) | Sep 9 12:20 → 6241 |
| 5406 | Sep 9 14:20 (1975) | Sep 12 11:20 → 4945 |

Before the deploy, the cost froze at escalation and stayed there. After it, the freeze ends at the stable timestamp. The cost-sync warning check flagged all five as "Stable … since the last sync", and no stable jumps show up before Sep 3.

**The inconsistency:** the code comment directly above the changed line still says "Determine the earliest relevant timestamp for cost calculation cut-off". The existing test `test_case_cost_stops_at_stable_time` only sets `stable_at`, so it never exercises the multi-timestamp case, which is why this passed review. The original design (from `200cd428`, and the escalation-only behavior before it) also cuts at the first event.

**Caveats:**
- I inferred the escalation timestamps from the freeze in the cost data. The logs don't contain the `escalated_at` values, so checking the database for these five cases would confirm it.
- The commit's intent is ambiguous. Its message says "latest status timestamp", so counting escalated time until stable may have been deliberate. If so, the problem is that it reprices cases that were already reported, not that the arithmetic is wrong. Whether to keep `max` is a product decision for you and finance.
- Two anomalies look unrelated to this and I did not investigate them: case 5363 dropped from 3425 to 1243 on Sep 5 09:20, and case 5264 dropped from 4643 to 3188 on Aug 29 15:20. Both predate the deploy.

I haven't changed any code. Once you decide between reverting to `min` and keeping `max` (and updating the comment and test), the warehouse rows for the affected cases will need a re-sync.

----- next turn -----

The fix is in: the cost cut-off is back to the earliest of the stable, escalated and closed timestamps. A regression test now covers the case that caused the jump, and it fails on the old code.

- **Fix:** `src/dispatch/case_cost/service.py:353` is back to `min(timestamps)`. The comment above it already said "earliest", so I left it alone.
- **Regression test:** `test_get_participant_role_time_seconds_stops_at_first_cutoff_event` in `tests/case_cost/test_case_cost_service.py`. It sets up a participant assigned three hours ago, a case escalated two hours ago, and a case marked stable one hour ago. It expects 3600 seconds, the time up to escalation. With `max` it returns 7200 and fails, which I confirmed by temporarily switching the line back and restoring it.
- **Tests:** `python -m pytest tests/case_cost` passes, 20 of 20. I didn't run the rest of the suite.

Two things I did not do:
- **Warehouse data:** the five affected cases (5264, 5284, 5327, 5363, 5406) still hold the inflated values in the finance warehouse. Those rows will need a re-sync, and I haven't touched the warehouse.
- **Commit:** nothing is committed. Tell me if you want a commit or PR, and I'll use the attribution lines from the system instructions.

----- next turn -----

The hourly TypeError is fixed. Projects with a NULL `annual_employee_cost` or `business_year_hours` now get a case cost, using the project model's defaults (50000 and 2080) for the missing value.

**Cause:** the `Column(default=...)` values on `Project` only apply when a row is inserted. Some projects have NULL in these columns, and `get_hourly_rate` (`src/dispatch/case_cost/service.py`) divides by them. Every such case raised during `calculate_cases_response_cost`. The per-case `try/except` kept the rest of the run going, so those cases just never got a cost. All 708 errors in `scheduler.log` come from this one line, and they all happened while the case was being costed.

**Changes:**
- `src/dispatch/project/models.py`: the two defaults are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST` and `DEFAULT_BUSINESS_YEAR_HOURS`. The column defaults and the Pydantic schema use them, so there's one source of truth.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` falls back to those constants for each missing value. Both cost models call it.
- `tests/case_cost/test_case_cost_service.py`: two new tests.
  - `test_get_hourly_rate_uses_project_defaults_for_missing_values` covers each combination of missing fields.
  - `test_calculate_case_response_cost_with_null_project_cost_settings` runs the path the scheduler runs and checks the classic cost (one hour at the default rate, 25).

**Verification:** with the fallback removed, both new tests fail. With it in place, `tests/case_cost` passes (22 tests). `tests/project`, `tests/case`, `tests/incident_cost` and `tests/case_cost` together pass (58 tests).

**Not changed:**
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division. I didn't see TypeErrors for it in `scheduler.log`, but it would fail the same way for a project with NULL values. It's a one-line change if you want it.
- `src/dispatch/individual/service.py` hardcodes the same two numbers. I left it alone; it could use the constants too.
- Projects with NULL values are still NULL in the database, and nothing backfills them. Nothing needs it for costs now, but you may want to set real values for those projects, since the defaults are assumptions.
- Nothing is committed.

----- next turn -----

## Recap

**1. Inflated case costs (classic and new cost models)**
- **Cause:** commit `20f33137` changed the cost cut-off in `get_participant_role_time_seconds` from the earliest of the stable, escalated and closed timestamps to the latest. For a case that was escalated and later marked stable, the cut-off moved from the escalation time to the stable time. The cost jumped retroactively, and the cost-sync job copied it to the warehouse.
- **Shipped by:** image `main-65f7df6e`, rolled out to the scheduler on 2025-09-02 at 18:14–18:15 UTC. The later images `main-51546e13` (Sept 4 and Sept 10) also contain the commit.
- **Evidence:** five cases (5264, 5284, 5327, 5363, 5406) had their cost frozen at escalation, then jumped on the first hourly run after they were marked stable.
- **Fix:** restored `min(timestamps)`. Added `test_get_participant_role_time_seconds_stops_at_first_cutoff_event`. It fails on the old `max` code.
- **Not yet done:** the warehouse rows for those five cases still hold the inflated values and need a re-sync.

**2. Hourly TypeError (cases with no cost, since Sept 8)**
- **Cause:** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. Some projects have NULL in `annual_employee_cost`, because the model default only applies on insert. Each affected case raised during the hourly run, and the error was logged and skipped.
- **Fix:** `get_hourly_rate` now falls back to the model defaults (50000 and 2080), which are now named constants in `project/models.py`. Added two tests. Both fail without the fallback.
- **Not changed:** `incident_cost/service.py:133` has the same unguarded division. It is not in the logs, but it would fail the same way.

**Verification:** `tests/case_cost` passes (22 tests). `tests/project`, `tests/case`, `tests/incident_cost` and `tests/case_cost` together pass (58 tests). Nothing is committed.

**Caveats for the report:**
- `FIRST_INFLATED` is the first date an inflated value appears in the logs (the Sept 3 run). The logs don't show escalation times, so a case inflated on the evening of Sept 2 couldn't be ruled out.
- The escalation timestamps for the five cases were inferred from the freeze pattern, not read from the database.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```