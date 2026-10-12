**Root cause:** commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, 2025-09-02). It changed one line in `get_participant_role_time_seconds()` in `src/dispatch/case_cost/service.py`, from `min(timestamps)` to `max(timestamps)`.

The timestamps are `stable_at`, `escalated_at` and `closed_at`. The cut-off decides when a participant's role stops accruing cost. Before the change it was the earliest of those timestamps, so an escalated case stopped accruing at escalation. Now it is the latest one. When a case that was escalated earlier is marked stable, `stable_at` becomes the latest timestamp and the cut-off moves forward. Every participant role's time is then recomputed over the longer window, and the cost jumps in one step. Cases that are closed after being stable get the same effect. Case 5363 shows it: it went from $2,261 to $6,241 in the 2025-09-09 12:20Z sync, flagged as `Stable`, +176%.

**Deploy:** the first production deploy containing the commit was image `registry.example.com/dispatch:main-65f7df6e`, on 2025-09-02. The db-upgrade pod pulled it at 18:14:09Z, and the scheduler pod at 18:15:10Z.
- The previous deploy, `main-3e0445ff` on 2025-08-27, does not contain `20f33137`.
- `main-51546e13` on 2025-09-04 also contains it, but it is not the first deploy to do so.
- The 2025-09-10 scheduler event is a pod restart on the same image, not a deploy.

**Evidence from the logs:**
- Before the deploy, `cost-sync.log` has no `costsync.checks` warnings. The only warning is an unrelated read-timeout retry on 08-31.
- After the deploy, the first flag is case 5284 (`Stable`) at 2025-09-03 11:20Z, +164% (3331 → 8804). That is the first sync after the deploy that saw a case newly marked stable.
- Later flags are 5363 on 09-09 and 5406 on 09-12, +150% (1975 → 4945). All flagged cases are `Stable`.
- Ordinary hourly increments on other cases (e.g. 1189 → 1226) are normal and unchanged.

**Ruled out:** case-cost-sync moved from 1.4.2 to 1.5.0 on 2025-09-01 at 10:20Z. That is before any jump, and nothing was flagged until 09-03. The page size also changed from 50 to 100 with it, which looks harmless. I did not read the sync's code, only its logs.

**Caveat:** I confirmed the commit by timing and by reading the diff. I did not recompute any case's cost with the old and new code. Whether `max` is a bug or an intended semantics change is a product question. The commit message calls it a fix, and the cost model's stable-case semantics changed without anyone telling finance.

I haven't changed any code.

----- next turn -----

I reverted the cut-off in `get_participant_role_time_seconds()` (`src/dispatch/case_cost/service.py`) from `max(timestamps)` back to `min(timestamps)`. Nothing is committed.

I added `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. It sets up a case that was escalated 3 hours ago, marked stable 2 hours ago and closed 1 hour ago, with an assignee who joined 5 hours ago. It asserts the role time stops at the escalation, so it covers the escalated-then-stable case that produced the cost jumps.

With the fix, all 20 tests in `tests/case_cost` pass. With the fix stashed (the old `max` code), the new test fails and the other 19 pass.

I only ran `tests/case_cost`, not the full suite.

Reverting the line stops new jumps once it's deployed. The costs already synced to the warehouse for cases flagged or marked stable since 2025-09-02 (e.g. 5284, 5363, 5406) are inflated. They will correct on the next hourly sync after the fix is live, assuming the sync overwrites changed rows. Finance may also want to re-check any figures they have already reported.

----- next turn -----

The TypeError is fixed in `get_hourly_rate()`, and `tests/case_cost` passes (22 tests). Nothing is committed.

**Cause:** `get_hourly_rate()` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Both columns on `Project` are nullable, and the project API schema accepts `None` for them. A project with a NULL value there makes the division fail. All 708 logged errors are `unsupported operand type(s) for /: 'NoneType' and 'int'`, so `annual_employee_cost` was the missing value in every one. The traceback goes through `calculate_case_response_cost_new`, so the new cost model hits it first.

The job's error handler logs each failure, so the affected cases are skipped each hour and never get a cost.

**Not determined:** why it started on 2025-09-08. The code that divides hasn't changed recently, and I found no commit that explains it. Most likely a project's cost settings were set to null, for example through the project update API, around then. That is a guess. You'd need to check the database for projects with NULL `annual_employee_cost`.

**Fix:** a missing value now falls back to the project model's own default, read from the column definition rather than copied into the code. That is currently 50000 for the annual cost and 2080 for the hours. Each value is handled independently, so a project missing only one keeps the other.

**Tests added:**
- `test_get_hourly_rate__missing_project_values_use_defaults` covers both missing, only the annual cost missing, and only the hours missing.
- `test_calculate_case_response_cost__project_without_cost_settings` runs a case through the new cost model on a project with neither value set.

With the fix stashed, both new tests fail. The earlier regression test from the `min`/`max` fix also fails in that run, since stashing `src` undoes that fix too. The 19 older tests pass either way.

**Not fixed:** `get_hourly_rate()` in `src/dispatch/incident_cost/service.py` has the identical division and would fail the same way for incidents. I left it alone because you asked about cases. It's a one-line-pattern change if you want it done.

----- next turn -----

## Recap

**What happened:** the finance warehouse's case costs were several times too high from early September. The cause was a one-line change in `20f33137` ("use the latest status timestamp as the cost cut-off"), which turned `min(timestamps)` into `max(timestamps)`. The timestamps are `stable_at`, `escalated_at` and `closed_at`. Before the change, a case stopped accruing cost at the earliest of them. After it, a case that was escalated and later marked stable kept accruing until `stable_at` (or `closed_at`). Costs then jumped in the sync after the status change. Case 5363 went from $2,261 to $6,241 on 2025-09-09.

**Shipped by:** image `registry.example.com/dispatch:main-65f7df6e`, deployed on 2025-09-02. The db-upgrade pod pulled it at 18:14Z and the scheduler pod at 18:15Z. The previous deploy, `main-3e0445ff` on 08-27, did not contain the commit. The 09-04 deploy `main-51546e13` also contains it, but it is not the first to ship it.

**First inflated case:** case 5284, flagged `Stable`, went from 3331 to 8804 (+164%) in the 2025-09-03 11:20Z sync. It is the first in the logs after the deploy. A scan of the diffs between the deploy and that sync found no earlier jump of that kind. This is the first jump in the logs, not a recomputation of every case's cost.

**Fixed:** the cut-off is back to `min`, with a regression test (`test_case_cost_stops_at_earliest_status_timestamp`). Costs already in the warehouse for cases marked stable since 2025-09-02 are inflated. They should correct on the next hourly sync once the fix is deployed, assuming the sync overwrites changed rows. Finance may want to re-check any figures they've already reported.

**Second issue, separate:** from 2025-09-08 the hourly scheduler job logged `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` 708 times. `get_hourly_rate()` in `src/dispatch/case_cost/service.py` divided `project.annual_employee_cost` by `project.business_year_hours`. Both columns are nullable, and the logged errors show the annual cost was the missing value. Affected cases got no cost. It now falls back to the project model's defaults (50000 and 2080) for each missing value, with two tests added. I did not determine why it began on 09-08. `incident_cost/service.py` has the same division and is not fixed.

**Not committed:** both fixes and their tests are uncommitted in the working tree. `tests/case_cost` passes (22 tests); I did not run the full suite.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost