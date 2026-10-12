Status: I've traced the cost jump to a commit and the deploy that shipped it. Here's what I found, without changing any code.

## Root cause

Commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, 2025-09-02), changed one line in `get_participant_role_time_seconds()` in `src/dispatch/case_cost/service.py`:

```diff
-            participant_role_renounced_at = min(timestamps)
+            participant_role_renounced_at = max(timestamps)
```

`timestamps` holds the case's `stable_at`, `escalated_at` and `closed_at`. The code is meant to stop charging participant time once the case leaves the active phase. With `min`, the cut-off was the first of those events, usually `stable_at`. With `max`, it is the last event. A case that was marked stable and later closed or escalated now keeps accruing cost for the whole gap between those two timestamps.

The commit message calls it a "fix", but it reverses the intended meaning of the cut-off. The code comment still says "Determine the **earliest** relevant timestamp", so the code and its comment now disagree.

## Evidence

- **Frozen, then jumped.** Case 5363's classic cost froze at 2261 from 2025-09-05 16:20 to 2025-09-09 12:20. At 2025-09-09 12:20 it jumped to 6241 in one sync. This fits a case whose cut-off moved from the early `stable_at` to a later timestamp.
- **I haven't confirmed what that later timestamp was.** The logs don't contain `closed_at` or `escalated_at`, so that part is inferred from the code.
- **Other flagged cases look the same.** `case-cost-sync` flagged five cases, and all of them are Stable:

  | Case | Date | Cost change |
  |---|---|---|
  | 5284 | 09-03 | 3331 → 8804 |
  | 5327 | 09-05 | 2244 → 5539 |
  | 5264 | 09-08 | 3285 → 11987 |
  | 5363 | 09-09 | 2261 → 6241 |
  | 5406 | 09-12 | 1975 → 4945 |

- **Nothing was flagged before the deploy.** There are no such jumps from 08-25 to 09-02. Cost drops in that period are routine, for example 9751 → 9120 on 08-25.
- **Likely not caused by the new sync version.** `case-cost-sync` moved from 1.4.2 to 1.5.0 on 2025-09-01 10:20. That is before the first jump, and the jumps arrive days apart, one case at a time. It also changed the page size from 50 to 100, but the diffs it logs are Dispatch's own values.

## The deploy

The first image containing `20f33137` was `registry.example.com/dispatch:main-65f7df6e`. It was the first rollout after the commit, and `65f7df6e` is the commit right after it on `main`. It reached production on **2025-09-02 at about 18:14–18:15Z**:

- A `dispatch-db-upgrade-65f7df6e` job completed at 18:14:33.
- Both `dispatch-web` and `dispatch-scheduler` were replaced at 18:14–18:15, with the scheduler starting on the new image at 18:15:24.

The scheduler is what recalculates the costs. `calculate_cases_response_cost` in `case_cost/scheduled.py` runs there and the API serves the stored result. The first flagged jump, case 5284, came on 09-03 at 11:20, the next day.

The later images, `51546e13` from 09-04 onward, still contain the change. `51546e13` is the current `HEAD`, so production is still affected.

## Other observations

- **Unrelated scheduler error.** From 2025-09-08 15:55, `case_cost.scheduled` logs `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` from `get_hourly_rate`. It looks like a different problem that hides cases from recalculation, and it is worth its own ticket.
- **The `Stable` skip doesn't help.** Stable cases whose cost was updated after `stable_at` are skipped, but a later close or escalation takes them off that path.

## Suggested next steps (not done)

1. Revert to `min`, or compute the cut-off per status. Take `stable_at` for stable cases, `escalated_at` for escalated cases and `closed_at` for closed cases, so the earliest event ends the accrual.
2. Recompute the costs of every case that is Stable, Escalated or Closed and was touched after 2025-09-02 18:15Z, and re-sync the finance warehouse. The affected set is larger than the five flagged cases, because the sync only flags jumps over about 100%.
3. Add a regression test with a case that is stable, then closed later.

I can prepare the fix and a backfill query when you want them.

----- next turn -----

I fixed it, and the new regression test fails on the old code and passes on the fix. I haven't committed anything.

- **Fix:** in `src/dispatch/case_cost/service.py`, `get_participant_role_time_seconds()` goes back to `min(timestamps)`. Cost now stops at the earliest of `stable_at`, `escalated_at` and `closed_at`, as it did before `20f33137`.
- **Test:** I added `test_case_cost_stops_at_earliest_status_timestamp` to `tests/case_cost/test_case_cost_service.py`. It covers a case that was stable and later closed, and one that was stable and later escalated. In both, the cost has to stop at `stable_at`. The old test only set `stable_at`, so it couldn't tell `min` from `max`.
- **Results:**
  - With the fix, all 20 tests in `tests/case_cost` pass.
  - With only the source change stashed, the new test fails (`32400.0 == 14400.0`, i.e. 9 hours charged instead of 4) and the other 19 pass.

The fix only changes what the scheduler computes from now on. The inflated costs already stored in Dispatch and synced to the finance warehouse are still there. Fixing them needs a recompute of every Stable, Escalated or Closed case touched since 2025-09-02 18:15Z, then a re-sync. The scheduler skips stable cases already updated after `stable_at`, so it may not correct those on its own. I can write that backfill if you want it. The unrelated `NoneType / int` error in `get_hourly_rate` since 09-08 is also still open.

----- next turn -----

The TypeError is fixed and the new tests pass. I haven't committed anything. The case, project, incident-cost and case suites all pass (58 tests).

**Cause.** `project.annual_employee_cost` and `project.business_year_hours` are nullable columns. `get_hourly_rate()` in `case_cost/service.py` divided them without checking for `None`. For a project where either value is NULL, every case in it failed with `NoneType / int`. I don't know how a project ended up with NULLs: the column defaults only apply on insert, and the project API schema accepts an explicit null. I also couldn't tell from the logs which project it is.

**Why it looked like "a few cases".** `calculate_cases_response_cost` catches the exception per case and logs it, so the rest of the loop keeps going. Those cases got no cost update at all.

**Fix.**
- `src/dispatch/project/models.py` now has `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The `Project` columns and the `ProjectBase` schema use them, so the values are the same as before and now live in one place.
- `get_hourly_rate()` in `src/dispatch/case_cost/service.py` falls back to those defaults separately for whichever value is `None`.

**Tests.** I added two to `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate_uses_project_defaults_for_missing_values` covers both values missing, only the cost missing, and only the hours missing.
- `test_calculate_case_response_cost_with_missing_project_cost_settings` runs the full case cost calculation on a project with NULL values.

With the source changes stashed, both fail, along with the earlier stable/closed test, and the other 19 tests pass.

- **Incident costs.** `incident_cost/service.py:131` has the same `get_hourly_rate` and the same bug. You only asked about cases, so I left it. It's a small change if you want it.
- **Existing NULLs.** The NULL values are still in the database. The code now tolerates them, but you may want to find and fix the project or projects that have them.
- **Recovery.** The affected cases will pick up costs on the next hourly run after deploy.

----- next turn -----

## Recap

**Cost inflation**
- Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`. That function sets the point where a case's participant time stops counting. The cut-off moved from the earliest of `stable_at`, `escalated_at` and `closed_at` to the latest. A case that was marked stable and later closed or escalated therefore kept accruing cost for the whole gap.
- The change reached production in image `dispatch:main-65f7df6e` on 2025-09-02 at about 18:14–18:15Z, when both the web and scheduler deployments rolled. The affected code is in the scheduler's hourly job.
- Cost-sync flagged five Stable cases for jumps of 147–265%, starting with case 5284 on 2025-09-03. Case 5363 was the 2261 → 6241 jump on 09-09.
- The 09-03 date is the earliest large jump in the sync log. I only checked for jumps over $600, so smaller inflations before that are possible. Because the stored costs are still wrong, they need a backfill. The fix is in the working tree and not committed or deployed.

**Hourly TypeError**
- The project's `annual_employee_cost` was NULL, so `get_hourly_rate()` divided `None` by an int. The error is logged per case and the loop continues, so those cases got no cost update.
- `get_hourly_rate()` now falls back to the project model defaults (50000 and 2080) for whichever value is missing.

**Changes, uncommitted**
- `src/dispatch/case_cost/service.py`: `min` restored, and the hourly-rate fallback added.
- `src/dispatch/project/models.py`: the default values are now named constants.
- `tests/case_cost/test_case_cost_service.py`: three regression tests, which fail on the old code.

**Open items**
- Backfill and re-sync the costs of every Stable, Escalated or Closed case touched since 2025-09-02 18:15Z.
- Find the project with NULL cost settings and fix its data.
- `incident_cost/service.py` has the same unguarded division.
- Nothing in the logs shows when the NULL value first appeared, but the errors begin 2025-09-08 15:55.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost