Root cause found and deploy identified. I've changed no code.

**Root cause: commit `20f33137`**, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, 2025-09-02 09:29 PDT). It changes one line in `get_participant_role_time_seconds()` in `src/dispatch/case_cost/service.py`:

```python
- participant_role_renounced_at = min(timestamps)
+ participant_role_renounced_at = max(timestamps)
```

- **What the code does:** the timestamps are `stable_at`, `escalated_at` and `closed_at`. They are the cut-off after which a participant stops accruing cost on a case that is no longer new or in triage.
- **Before:** the cut-off was the earliest of them. A case marked stable stopped accruing at `stable_at`, even if it was escalated or closed later.
- **After:** the cut-off is the latest of them. A stable case's participants keep accruing until a later `escalated_at` or `closed_at`, or until now if there is none.
- **Why the cost jumps:** the rest of the cost calculation is untouched. Once a case becomes stable, its classic cost is computed over a much longer window, so the number jumps. The `HOURS_IN_DAY` work-day discount in that function grows more slowly than the extra hours.
- **Rates and models:** the hourly rates and cost models are unchanged, as you said.

**Deploy that shipped it: image `dispatch:main-65f7df6e`, 2025-09-02 ~18:14–18:16 UTC.**
- The events log shows `dispatch-db-upgrade-65f7df6e` completing at 18:14:33Z.
- It then shows `dispatch-web` rolling over to `dispatch-web-zrhzjwmzrh` and `dispatch-scheduler` to `dispatch-scheduler-qdd74fpnsl`, both on that image.
- The previous image, `main-3e0445ff` (deployed 2025-08-27), predates the commit.
- `20f33137` is an ancestor of `65f7df6e`, so that was the first production image to contain it.
- The later deploy of `main-51546e13` (2025-09-04 16:52Z and again 2025-09-10 03:12Z) also contains the change, but it didn't introduce it.

**Evidence in the logs**
- Before 2025-09-02 18:15Z, `cost-sync.log` has no `costsync.checks` anomaly warnings. The only WARNING before 09-02 is an unrelated read timeout on 08-31.
- The first flagged case is 5284 on 09-03 11:20Z, with classic cost 3331 → 8804 (+164%). Later flags include 5327 on 09-05 and 5406 on 09-12 (+150%).
- Case 5363 (`dispatch-default-security-5363`) is the one you cited. It rose steadily from 131 on 09-04. When it was marked Stable on 09-09 12:20Z, its classic cost went from 2261 to 6241 (+176%).
- Every flagged case is in `Stable` status, which matches the `stable_at` path through the changed line.

**Not the cause**
- The `NoneType / int` errors in `scheduler.log` (from 09-06 and 09-08) are a different problem. `project.annual_employee_cost` is None in `get_hourly_rate`, and the failure is in the new cost model.
- The 09-04 and 09-10 deploys were not the origin.
- The finance sync only copies the values Dispatch's API returns. The inflated numbers come from Dispatch, not from the sync job.

The commit message says "latest", so the author may have meant to fix a different case, for example one escalated and then stabilised. The fix is likely to restore `min()`, or to pick the cut-off by status. Already-synced warehouse values for stable cases will also need recalculating. Do you want me to prepare the code change?

----- next turn -----

I fixed it by reverting `max(timestamps)` back to `min(timestamps)` in `get_participant_role_time_seconds()` (`src/dispatch/case_cost/service.py`). A case's cost stops accruing at the earliest of `stable_at`, `escalated_at` and `closed_at` again.

The new regression test is `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. It sets up a case that was marked stable 8 hours ago and closed 2 hours ago, with a participant who took the role 10 hours ago. Only the 2 hours before the case became stable should count.

- **Before the fix:** the test failed with 28800 seconds (8 hours) against the expected 7200.
- **After the fix:** all 20 tests in `tests/case_cost` pass.

The existing stable-time test missed the bug because it only set `stable_at`. With a single timestamp, `min` and `max` give the same answer. The new test uses two timestamps.

I did not commit anything.

This only fixes the calculation in new code. Dispatch should recompute stable cases once the fix is deployed. The finance team should then re-sync the inflated warehouse values for cases marked stable since 2025-09-02. The warnings in `cost-sync.log` list the ones that were flagged. Cases that were never flagged may also be affected.

----- next turn -----

The TypeError is fixed: a project with an unset annual employee cost or business year hours now falls back to the project model's default, so its cases get a cost. The new test and the existing case and incident cost tests pass (36 tests).

**Cause.** `get_hourly_rate()` in `src/dispatch/case_cost/service.py` computed `project.annual_employee_cost / project.business_year_hours`. At least one project has one of those two columns set to NULL. The columns are nullable, and the API schema (`ProjectBase`) accepts `None` for both. When that happens, the division raises `unsupported operand type(s) for /: 'NoneType' and 'int'`. The traceback is `calculate_case_response_cost_new` → `get_hourly_rate`, so it comes from the new cost model.

The scheduler catches the error per case, so only cases in the affected project fail each hour. That project's cases get no updated cost, and `scheduler.log` shows 1,416 occurrences. I couldn't see from the logs why the value became NULL on 09-08. Most likely someone cleared the field in the project settings, but that is a guess.

**Fix.** `get_hourly_rate()` now substitutes the model defaults, 50000 and 2080, for a missing value. The defaults are read from the `Project` column definitions, so they aren't duplicated. Zero business year hours also falls back, which avoids a division by zero.

**Test.** `test_get_hourly_rate__project_settings_unset` covers a normal rate, a missing cost, missing hours, and both missing.

Two things to check:
- `incident_cost/service.py:133` has the identical line and would fail the same way if an incident's project has a NULL setting. I left it alone because you asked about cases. It's a one-line follow-up if you want it.
- The project's NULL setting is still there. You may want to set it to a real value in the project settings.

Nothing is committed. The working tree also still holds the earlier `min` fix and its test.

----- next turn -----

## Recap

**Cost inflation**
- Since early September, the finance warehouse showed case response costs several times higher than before for cases marked stable. One example is `dispatch-default-security-5363`, which went from $2,261 to $6,241 on 2025-09-09.
- Commit `20f33137` ("use the latest status timestamp as the cost cut-off", 2025-09-02) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`. That moved the cost cut-off for a stable case from `stable_at` to the latest of `stable_at`, `escalated_at` and `closed_at`, or to now if only `stable_at` is set. Participants on stable cases kept accruing cost.
- The first production image containing the commit was `dispatch:main-65f7df6e`, rolled out around 18:14–18:16 UTC on 2025-09-02. The next image, `main-51546e13`, also contains it but did not introduce it.
- The first flagged inflation is case 5284 on 2025-09-03 at 11:20Z (3331 → 8804, +164%). The earlier hourly diffs after the deploy look like normal growth on active cases.
- I reverted to `min(timestamps)` and added `test_case_cost_stops_at_earliest_status_timestamp`. It failed before the fix and passes after.

**Hourly TypeError (separate issue)**
- Since 2025-09-08, `get_hourly_rate()` raised `unsupported operand type(s) for /: 'NoneType' and 'int'` for cases in a project with a NULL setting. The scheduler caught the error per case, so only that project's cases lost their cost update.
- The error message names `NoneType` as the dividend, so the missing value is `annual_employee_cost`. A missing `business_year_hours` would have produced an `int` and `NoneType` message.
- The fix falls back to the project model defaults (50000 and 2080) when either value is missing. The test is `test_get_hourly_rate__project_settings_unset`.

**Open items**
- Nothing is committed yet.
- Stable cases need recalculating once the fix is deployed, and the warehouse needs re-syncing for cases marked stable since 2025-09-02.
- `incident_cost/service.py:133` has the same unguarded division.
- I could not tell from the logs why the project's value became NULL.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost