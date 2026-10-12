**Root cause:** commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, 2025-09-02), is what inflated the costs. It shipped to production in the deploy at 2025-09-02 18:14–18:15Z.

**The change**
- In `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`), the cost cut-off changed from `min(timestamps)` to `max(timestamps)`.
- The timestamps are `stable_at`, `escalated_at` and `closed_at`.
- The code's own comment still says "earliest relevant timestamp".
- Before, a case's cost stopped growing at the first of those events. Now it keeps accruing until the last one.
- A case that is marked stable and later closed or escalated is billed for the whole gap. The cost never goes back down.
- This is a logic change, not a rate or cost-model change, which fits what you saw.
- The commit message calls it a "fix", but it reverses the intent the code still documents.

**The deploy**
- `events.log` shows an image rollout of `registry.example.com/dispatch:main-65f7df6e` at 2025-09-02 18:14Z. The db-upgrade job ran first, then the web pods, then the scheduler pod at about 18:15Z.
- `65f7df6e` is a descendant of `20f33137` (`git merge-base --is-ancestor` confirms it). The previous image, `main-3e0445ff` from 08-27, does not contain it.
- `main-51546e13` was deployed on 09-04 at 16:52Z and also contains the change. It is not the first deploy that carried it.

**Evidence from the logs**
- **Flags:** `case-cost-sync` flagged no cost jumps from 08-25 to 09-02. After the deploy, it flagged five Stable cases with jumps of +147% to +265%. The first was case 5284 on 09-03 at 11:20Z. The others were 5327 (09-05), 5264 (09-08), 5363 (09-09) and 5406 (09-12).
- **Cost-sync version:** it moved from 1.4.2 to 1.5.0 on 09-01, a day before the Dispatch deploy. Costs were normal for a day afterwards, so I'm ruling it out.
- **Other deploys:** no other deploy or cronjob change lines up with the jump.

**Gaps**
- The logs don't show each case's status timestamps. I inferred the mechanism from the code and from the flags only affecting Stable cases. I did not confirm it against `stable_at`, `escalated_at` and `closed_at` for case 5363 or the other four cases.
- For 5363 specifically, its cost stopped growing at 09-05 16:20Z. You said it was marked stable on 09-09. I couldn't reconcile the two from the logs alone.
- Smaller drops in the cost-sync diffs also appear before the deploy, so they are normal noise. I don't treat them as part of this issue.

**Impact and next steps**
- Every Stable, escalated or closed case that has a later timestamp has been overstated since 09-02, not only the five that were flagged.
- Fixing it means reverting to `min`, or replacing the logic with an explicit rule for which timestamp ends a case. Either way the warehouse rows synced since 09-02 need recomputing.
- I haven't changed any code.

----- next turn -----

I fixed the cost cut-off and added a regression test. The `tests/case_cost` suite passes (20 tests) with the fix.

- **Fix:** in `src/dispatch/case_cost/service.py`, the cut-off is `min(timestamps)` again. A case's cost now stops at the earliest of `stable_at`, `escalated_at` and `closed_at`, instead of the latest.
- **Test:** `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py` covers a case that went stable an hour ago and was closed 10 minutes ago. It asserts the role time stops at `stable_at`. With the fix stashed it fails, because the time runs on to the close time.

I only ran `tests/case_cost`, not the whole suite. I haven't committed anything.

Two follow-ups are still open:
- **Deploy:** the fix has to reach production.
- **Warehouse:** the finance warehouse rows synced since 2025-09-02 need recomputing. Those are costs for Stable, escalated and closed cases, so they affect more than the five cases that were flagged.

----- next turn -----

The TypeError is fixed, and the `tests/case_cost` suite passes (22 tests). I didn't run the rest of the suite and haven't committed anything.

**Cause**
- `get_hourly_rate` divided `project.annual_employee_cost` by `project.business_year_hours`. When either value is NULL on a project, that is `None / int`, which raises the TypeError.
- The traceback in `scheduler.log` goes through `calculate_cases_response_cost`, then `update_case_response_cost`, then `calculate_case_response_cost_new`, and ends in `get_hourly_rate`. One failing case is logged as an ERROR each time, so cases for that project get no cost.
- The `fraud` project first shows up in the scheduler log at 2025-09-08 14:54, and the first TypeError is at 15:55. So I believe `fraud` was created around then with the cost fields unset. The log doesn't name the failing project, so that link is inferred.
- The project create schema allows `None` for both fields (`annual_employee_cost: int | None = 50000` in `project/models.py`). An explicit null presumably overrides the default and the column stores NULL. I didn't verify the API path.

**Fix**
- In `src/dispatch/case_cost/service.py`, `get_hourly_rate` now uses the Project column default (50000 and 2080) for whichever value is `None`. It reads them from the model rather than hardcoding them.
- Two new tests cover it: the first checks the four combinations of set and unset values, and the second runs `calculate_case_response_cost_new` on a project with both values unset. Both fail without the fix.

**Not changed**
- `incident_cost/service.py:131` has an identical `get_hourly_rate` with the same bug. I left it alone because you asked about the case cost job.
- Nothing stops new projects from being saved with NULL in these fields. The cleanest long-term fix is to reject `None` in the project schema and backfill the existing NULL rows. Say if you want either.

----- next turn -----

The cost bug is a one-word change in the case cost cut-off, and the hourly TypeError is a separate bug.

**Cost inflation**
- Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` for the cost cut-off in `get_participant_role_time_seconds`. A case's cost then ran on to its latest status timestamp instead of stopping at its first.
- That commit reached production in the `main-65f7df6e` rollout on 2025-09-02 at about 18:14Z.
- The first inflated case I can see in the logs is 5284 on 2025-09-03 at 11:20Z. Its classic cost went from 3331 to 8804, and `case-cost-sync` flagged it.
- The cost-sync diffs between the rollout and that sync show no unusual jumps, but a smaller inflation could be hidden in normal hourly noise. If you need an exact first-inflated case, check the `stable_at`, `escalated_at` and `closed_at` timestamps in the database.
- The fix, a revert to `min` plus a regression test, is in the working tree, uncommitted.
- Costs synced to the warehouse since 2025-09-02 need recomputing.

**Hourly TypeError**
- `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. A project saved with a NULL cost setting made the scheduler's hourly case cost job raise `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`.
- The `fraud` project appears in the scheduler log around 2025-09-08 14:54, and the first error is at 15:55. I believe `fraud` is the project with the NULL setting, but the log doesn't name it.
- The error text shows the numerator was `None`, so `annual_employee_cost` is the missing setting. If `business_year_hours` was also NULL, the message would be the same, so I can't rule that out.
- The fix falls back to the Project model defaults (50000 and 2080), with tests. It's in the working tree, uncommitted.
- `incident_cost/service.py` has the same unguarded division and is unchanged.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost