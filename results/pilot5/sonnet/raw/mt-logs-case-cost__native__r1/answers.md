Root cause: the commit `20f33137` changed `min` to `max` in the cost cut-off. It first reached production in the deploy of image `main-65f7df6e` on 2025-09-02 at 18:14 UTC. I haven't changed any code.

**Root cause**

- The commit is "fix(case_cost): use the latest status timestamp as the cost cut-off", by Jordan Lee, committed 2025-09-02 09:29 PDT.
- It changes `participant_role_renounced_at = min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`).
- That function gathers `stable_at`, `escalated_at` and `closed_at`, and uses the result as the point where a participant's time on a case stops counting.
- With `min`, cost stopped accruing at the earliest of those status timestamps. With `max`, it keeps accruing until the latest one.
- The classic cost is recomputed from scratch each time, so any case with more than one of those timestamps is re-priced upward as soon as the later one is set. Hourly rates and cost models are untouched, which matches what you saw.
- The `min` was not a bug. The code comment above it still describes the old behavior: "we use the role's renounced_at time if it happened before the case was marked as stable or closed".

**The deploy**

The three Dispatch deploys in the logs are:

| Deploy | Time (UTC) | Contains `20f33137`? |
|---|---|---|
| `main-3e0445ff` | 2025-08-27 17:03 | No |
| `main-65f7df6e` | 2025-09-02 18:14 | Yes, this is the one that shipped it |
| `main-51546e13` | 2025-09-04 16:52 | Yes, it carries the fix forward |

- `main-65f7df6e` is the commit right after the fix, and it rolled out cleanly: db-upgrade completed and the web and scheduler pods were replaced. Its build also included the `5670487c` dependabot removal, `beb60cc4` (entity JSONPath) and `65f7df6e` (UI channel filter), none of which touch case cost.
- `main-51546e13` is a second deploy that also contains the bug. Rolling back to it, or only to the commit before it, would not remove the bug.
- The scheduler pod was recreated again on 2025-09-10 with the same image; that isn't a new version.

**Evidence in the logs**

- **Before the deploy:** when a case went stable, its classic cost dropped because accrual froze at the earliest timestamp. For example, case 5224 went from 5753 to 3571 on 08-25.
- **After the deploy:** the first jump is case 5284 on 09-03 at 11:20, from 3331 to 8804. Later jumps:
  - Case 5327 on 09-05, from 2244 to 5539.
  - Case 5264 on 09-08, from 3285 to 11987.
  - Case 5363 on 09-09 at 12:20, from 2261 to 6241.
- cost-sync flagged only these five cases at the +147% threshold. Many others rose by smaller amounts (the second `costsync.diff` lines on 09-09 show it, for example case 5349 and 5384).
- **Case 5363:** it rose about $145 per hour until 09-05 16:20. It then stayed at 2261 for roughly four days, which I read as accrual frozen at an earlier status timestamp. Once the later timestamp existed (the case was marked stable on 09-09), `max` moved the cut-off forward and the cost jumped to 6241.
- I haven't confirmed which timestamp was set when for 5363, because the logs don't include the case status history.

**Not the cause**

- case-cost-sync went from 1.4.2 to 1.5.0 on 2025-09-01. That only changed the page size from 50 to 100 and the log format, and costs were unchanged for about a day afterwards.
- The Kubernetes warnings (web readiness-probe timeouts during HPA scale-ups, the 502 on the image pull during the 08-27 deploy) are unrelated.

**Impact**

- The warehouse rows for every case with more than one status timestamp since 09-02 18:14 UTC are inflated.
- Cases that were already stable then, and whose roles have no `renounced_at`, may also have shifted.
- Those rows will keep the inflated values until Dispatch computes the right ones and cost-sync re-syncs them.

**Next step**

When you want me to make the change, the fix is to restore `min` (a revert of `20f33137`) and deploy it, then have finance backfill the affected cases. If the original intent was "keep counting until the case is closed", that needs a deliberate rule rather than `max` over all three timestamps, which I'd want to discuss first.

----- next turn -----

I reverted the `max` back to `min` in `src/dispatch/case_cost/service.py:353`, and the case_cost tests pass (20 passed). I haven't committed anything.

**New test:** `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py` builds a closed case with `stable_at`, `escalated_at` and `closed_at` set at different times. It asserts the cost stops at the earliest one, `stable_at`. I ran it against the buggy `max` version and it fails there.

The existing stable-time test only sets `stable_at`, so `min` and `max` gave the same result and it couldn't catch this.

**Deploy and cleanup (not done):**
- The fix still needs to be deployed.
- The warehouse rows for affected cases are still inflated until the fix is live and cost-sync has re-synced them. Finance should check the flagged cases, 5284, 5327, 5264 and 5363, as well as the smaller increases.
- I left the stale comment above that line (the "we use the role's renounced_at time if it happened before the case was marked as stable or closed" one) as it was, since it describes the restored behavior.

----- next turn -----

The TypeError comes from `get_hourly_rate` dividing a project's `annual_employee_cost` when it is NULL. I fixed it so it falls back to the project model's defaults. The case_cost and project tests pass (27 passed), and the new test fails without the fix. Nothing is committed.

**Cause**
- Every one of the 708 TypeErrors in `scheduler.log` since 2025-09-08 15:55 is the same: `unsupported operand type(s) for /: 'NoneType' and 'int'`. Its traceback runs through `calculate_case_response_cost_new` and ends at `get_hourly_rate` in `src/dispatch/case_cost/service.py`.
- The numerator, `annual_employee_cost`, is None. The `Project` columns are nullable and their defaults of 50000 and 2080 only apply when a value isn't supplied at insert. `ProjectBase` also allows `None`.
- The exception is raised before any cost is saved, so those cases got no cost update at all. The hourly job only logs the error and moves on.
- I can't tell from the logs which project has the NULL; the log lines don't name it.

**Fix**
- `get_hourly_rate` now uses the default for whichever of the two values is None. The two defaults are now constants, `DEFAULT_ANNUAL_EMPLOYEE_COST` and `DEFAULT_BUSINESS_YEAR_HOURS`, in `src/dispatch/project/models.py`. The column and schema defaults use them too, so the numbers aren't duplicated.
- The new test is `test_get_hourly_rate__missing_values_use_project_defaults`. It checks each value missing, and both missing.

**Not addressed**
- A `business_year_hours` of 0 would still raise ZeroDivisionError. I only handled "not set".
- The affected project's data probably still has NULLs, and nothing stops them from being written again.
- Once this is deployed, those cases will get their first cost calculated at the default rate of $25 an hour. Finance will see new or changed rows for them.

----- next turn -----

## Recap

**Cost bug.** Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", committed 2025-09-02 09:29 PDT) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function gathers `stable_at`, `escalated_at` and `closed_at` to decide where a case's cost stops. With `max`, cost kept accruing until the latest of those timestamps, so cases with more than one of them were re-priced upward. Rates and cost models never changed.

**Deploy.** The fix first reached production in the Dispatch deploy of `main-65f7df6e` on 2025-09-02 at about 18:14 UTC. `main-51546e13` on 2025-09-04 also contained it. The earlier deploy `main-3e0445ff` (2025-08-27) did not.

**Impact.** The first inflated cost is case 5284 on 2025-09-03 at 11:20 UTC (3331 to 8804). No jump of that size appears between the deploy and that sync. Later jumps:
- 5327: 2244 to 5539 on 09-05.
- 5264: 3285 to 11987 on 09-08.
- 5363: 2261 to 6241 on 09-09.
- 5406: 1975 to 4945 on 09-12.

The sync also flagged 5406 on 09-12 at 11:20, a fifth flagged case I hadn't listed before.

Smaller inflations happened on other cases and aren't in this list. I checked jumps of more than 30% and more than $400, which is a threshold I picked, not a log field.

**Fixes (in the working tree, not committed or deployed).**
- The bug is reverted to `min`, with a regression test, `test_case_cost_stops_at_earliest_status_timestamp`.
- The separate hourly TypeError (708 occurrences since 2025-09-08 15:55) came from a project with `annual_employee_cost` NULL. `get_hourly_rate` now falls back to the project model's defaults of 50000 and 2080. Its test is `test_get_hourly_rate__missing_values_use_project_defaults`.

**Follow-ups.**
- Deploy the fix.
- Have finance re-sync the affected cases.
- Check which project has the NULL cost setting.
- A `business_year_hours` of 0 would still divide by zero.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost