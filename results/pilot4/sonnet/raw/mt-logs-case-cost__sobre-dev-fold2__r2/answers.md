**Root cause:** commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, 2025-09-02 09:29 PDT). It changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py`:

```diff
-            participant_role_renounced_at = min(timestamps)
+            participant_role_renounced_at = max(timestamps)
```

- **What the code does:** `timestamps` holds `stable_at`, `escalated_at` and `closed_at`, and it is the cut-off for how long each participant's role time is billed. The surrounding comment still says "earliest relevant timestamp", and a later check still assumes the cut-off is the earliest event.
- **Effect of the change:** with `max`, any non-new, non-triage case is billed up to its latest status timestamp instead of its earliest. A case that has a later `closed_at` or `escalated_at` set therefore keeps accruing role time after it went stable.
- **Why only Stable cases are inflated:** cases still in new or triage are untouched, because they are billed up to now either way.
- **Mismatch with the commit message:** the commit message sounds like a cleanup, but the change alters the billing semantics.

**Deploy that shipped it:** `registry.example.com/dispatch:main-65f7df6e`, rolled out on 2025-09-02 at about 18:14–18:15Z.
- The `dispatch-db-upgrade-65f7df6e` job completed at 18:14:33Z.
- The web pods were replaced from 18:14:36Z.
- The scheduler was replaced at 18:15:09Z.

Commit `65f7df6e` is the first commit after `20f33137` in history, so it is the first image to contain the change. The earlier production image, `main-3e0445ff` (2025-08-27), predates it. The later `main-51546e13` deploy on 2025-09-04 only carried it forward. The scheduler restart on 2025-09-10 reused the same image.

**Evidence from the logs:**
- `cost-sync.log` has no "flagged for review" warnings before the deploy. The first one is case 5284 on 09-03 at 11:20 (Stable, +164%), then 5327 on 09-05, 5264 on 09-08 (+265%) and 5363 on 09-09.
- Case 5363 went from $2,261 to $6,241 in the 09-09 12:20 sync, when it became Stable.
- The finance job is not the cause. `case-cost-sync` stayed on image 1.4.2 throughout and only copies what the API returns.

**What I couldn't confirm:** the logs don't contain the case timestamps. So I can't say which timestamp pushed 5363's cut-off later. A stale or later `escalated_at` or `closed_at` is my best guess, since `stable_at` alone would give the same result under `min` and `max`. Checking those fields for 5363 in the database would confirm it.

**Fix direction (no code changed):** revert to `min`, or choose the intended cut-off deliberately and fix the comment. Then recompute the costs of cases that went Stable since 2025-09-02, which the warehouse has been copying hourly.

----- next turn -----

I've reverted the `max(timestamps)` change back to `min(timestamps)` in `src/dispatch/case_cost/service.py`, and added a regression test.

- **Test:** `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. It sets `stable_at`, `escalated_at` and `closed_at` to different times on a closed case with a still-active role. It asserts that billed time stops at the earliest one, `stable_at`. The existing stable-time test only set `stable_at`, so `min` and `max` gave the same result and it couldn't catch the bug.
- **Results:** with the fix, all 20 tests in `tests/case_cost` pass. With the fix stashed, the new test fails, while the other 19 still pass.
- **Not committed:** the changes are in the working tree only.
- **Still to do:**
  - **Deploy:** this still has to ship to production.
  - **Recompute:** costs for cases that went Stable since 2025-09-02 need recomputing. The warehouse has been receiving inflated values from the hourly sync since the 09-02 deploy.

----- next turn -----

The TypeError is fixed, and the two new tests pass.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Both columns are nullable, and `project.service.update` copies explicit `None` values from the API straight onto the project. So when a project has either value unset, the division raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The traceback is `calculate_cases_response_cost` → `update_case_response_cost` → `calculate_case_response_cost_new` → `get_hourly_rate`. The 708 occurrences in `scheduler.log` come from this one path.

I don't know why it started on September 8. The logs show no code deploy then, so my best guess is a project setting was cleared that day. The logs don't say which project or who changed it. Querying `project` for NULL values in those two columns would confirm.

**Fix:** `get_hourly_rate` now uses the `Project` model's column default for whichever value is missing (50000 for annual cost, 2080 for business-year hours). A value that is set is kept.

**Tests**, in `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate__missing_project_settings_use_defaults` covers both values missing, only the cost missing, and only the hours missing.
- `test_calculate_case_response_cost__project_without_cost_settings` runs a full case cost calculation on a project with both values `None`.

All 22 tests in `tests/case_cost` pass. With the source changes stashed, both new tests fail. That stash also reverted the earlier `min`/`max` fix, so that test failed too.

**Not changed:**
- **`incident_cost`:** it has an identical `get_hourly_rate` and the same latent crash, but you only asked about cases.
- **Case update loop:** the exception skips that case on each run. I haven't checked whether it aborts the rest of the loop, so I can't say whether other cases were affected.
- **Commits:** nothing is committed.

----- next turn -----

## Recap

**Cost inflation**
- **Cause:** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function sets the cut-off for how long each participant's role time is billed. With `max`, any non-new, non-triage case with a later `closed_at` or `escalated_at` keeps accruing role time after it went stable.
- **Deploy:** the first image containing it was `main-65f7df6e`, rolled out on 2025-09-02 at about 18:14–18:15Z. The 09-04 `main-51546e13` deploy only carried it forward.
- **Detection:** the finance job's first "flagged for review" warning was case 5284 on 2025-09-03 at 11:20Z (+164%). There was one before 09-09 for case 5363 ($2,261 → $6,241), plus 09-05 and 09-08.
- **Fix:** I reverted the line to `min`. The regression test `test_case_cost_stops_at_earliest_status_timestamp` fails without the fix.

**Hourly TypeError**
- **Cause:** `get_hourly_rate` divides `project.annual_employee_cost` by `project.business_year_hours`. The error was `NoneType / int`, so the missing value was the numerator, `annual_employee_cost`. A missing `business_year_hours` would crash the same line with a different message.
- **Fix:** it now falls back to the `Project` model default for whichever value is missing. The new tests are `test_get_hourly_rate__missing_project_settings_use_defaults` and `test_calculate_case_response_cost__project_without_cost_settings`.
- **Open question:** the logs don't show why it began on 2025-09-08. No deploy happened then, so a project setting was probably cleared. That is a guess.

**Caveats**
- **First inflated date:** the log contains only the 2025-09-03 flagged diffs. Smaller inflation of a Stable case could have been synced between the 09-02 deploy and that warning. I saw no such jumps, but the logs don't prove there weren't any.
- **Not shipped:** the fixes aren't committed or deployed. Costs for cases that went Stable since 2025-09-02 still need recomputing.
- **Not changed:** `incident_cost` has the same unguarded `get_hourly_rate`, which I left alone.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost