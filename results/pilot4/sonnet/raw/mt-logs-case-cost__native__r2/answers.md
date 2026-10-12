**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02) changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py`. The line `participant_role_renounced_at = min(timestamps)` became `max(timestamps)`.

**Deploy:** it first reached production in `dispatch:main-65f7df6e`, rolled out on 2025-09-02 at about 18:14–18:15Z. I did not check whether this was an automatic release.
- The db-upgrade job `dispatch-db-upgrade-65f7df6e` ran at 18:14Z.
- The `dispatch-web` and `dispatch-scheduler` deployments then rolled to that image. The scheduler restarted at 18:15:30Z, per `scheduler.log`.
- The previous production image, `main-3e0445ff` (Aug 27), does not contain the commit. `main-65f7df6e` and the later `main-51546e13` (Sep 4) both do.
- The scheduler restart on Sep 10 reused `main-51546e13`, so it was a restart, not a new deploy.

**Why costs inflate:** the function takes the earliest of `stable_at`, `escalated_at` and `closed_at` as the point where a participant's response time stops counting. With `min`, the clock stops the first time the case leaves triage. With `max`, it runs until the latest of those timestamps.
- A case that went stable and was then closed, or escalated, now accrues cost until the later event.
- The function also applies a 24-hour day-cap discount, but the extra elapsed time still adds a lot.
- This is a logic change in Dispatch's own cost calculation. The hourly rates and cost models did not change.

**Evidence from the logs:**
- **Flagged cases:** all five `costsync.checks` warnings are Stable cases with jumps of +147% to +265%.
  - 5284 on Sep 3, 5327 on Sep 5 and 5264 on Sep 8.
  - 5363 on Sep 9, from 2261 to 6241.
  - 5406 on Sep 12.
- **Timing:** the first warning is Sep 3 at 11:20Z, the first hourly sync after the Sep 2 deploy where a case went stable. Before that there are no flags. The log has no `costsync.checks` warning before Sep 3.
- **Other cases:** those cases grew by about $100–150 per hour while active (5363 did, from 131 on Sep 4). They jump only when `stable_at` is set. That is the point where the cut-off changes, so the cost no longer freezes.

**Ruled out:** case-cost-sync moved from 1.4.2 to 1.5.0 on Sep 1 at 10:20Z. That changed the page size from 50 to 100, but it was a day before the first anomaly. The sync also just copies whatever the API returns.

**Caveats:**
- I didn't run the code against real case data. The link between the commit and the jumps rests on the code, the timing and the pattern in the logs.
- Case 5363 also dropped from 3425 to 1243 on Sep 5 at 09:20Z, and I haven't explained that. It happened before the Sep 9 spike and may be a separate effect.
- Warehouse rows for cases that went stable or were closed after Sep 2 18:15Z are likely overstated. They need recomputing after a fix, which means reverting to `min` or otherwise re-checking the intended cut-off.

I haven't changed any code.

----- next turn -----

I fixed the bug and added a regression test. All 20 tests in `tests/case_cost` pass with the fix. I haven't committed anything.

- **Fix:** in `src/dispatch/case_cost/service.py`, `get_participant_role_time_seconds` uses `min(timestamps)` again, so cost stops at the earliest of `stable_at`, `escalated_at` and `closed_at`.
- **Test:** `test_case_cost_cut_off_is_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. It builds a closed case that went stable first and was escalated and closed later. It expects the cost to stop at `stable_at`. It fails with `max` and passes with `min`. I confirmed this by stashing the fix and re-running.
- **Why the old tests missed it:** they only set `stable_at`, so `min` and `max` gave the same answer.

- **Warehouse rows:** the costs already written to the finance warehouse are still inflated. The sync only upserts rows whose cost changed, so once the fix is deployed it will correct a case only if its cost still changes. Cases that are already stable or closed are frozen, so their rows won't change. Finance needs a backfill for cases that went stable, escalated or closed after Sep 2, 18:15Z.
- **Case 5363:** the unexplained Sep 5 drop from 3425 to 1243 is still unexplained, so check it separately.
- **Original intent:** commit `20f33137` said it wanted "the latest status timestamp". I read that as a mistake, since the code comment and the tests describe the earliest cut-off. If there was a real reason for it, such as cost for escalated cases, it needs a different design.

----- next turn -----

The `TypeError` is fixed, and cases in projects with missing cost settings now get a cost. All 25 tests in `tests/case_cost` pass. I haven't committed anything.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Cases in a project where `annual_employee_cost` is `NULL` fail with `unsupported operand type(s) for /: 'NoneType' and 'int'`.
- **Logs:** `scheduler.log` has 708 identical errors, starting Sep 8 at 15:55Z and repeating hourly. They all come from `calculate_case_response_cost_new` (line 466) through `update_case_response_cost`. All 708 are `None / int`, so only `annual_employee_cost` was missing. No `int / None` errors appear, so `business_year_hours` was never the culprit in these logs.
- **Why it can be NULL:** the model's column defaults (50000 and 2080) only apply when a project is created without a value. The project pydantic schema allows `None`, so a project update can store `NULL` explicitly. Nothing in the logs says which project or case it is, so I can't say what changed on Sep 8. No deploy happened then, so it looks like a data change.
- **Not related to the cost spike:** the error is a separate bug, not caused by the `min`/`max` change.

**Fix:** `get_hourly_rate` now takes each missing value from the `Project` column default, read via `Project.annual_employee_cost.default.arg` and `Project.business_year_hours.default.arg`. These are 50000 and 2080, so nothing is hard-coded.

**Tests:** I added two tests to `tests/case_cost/test_case_cost_service.py`.
- A parametrized `get_hourly_rate` test covers a missing cost, missing hours, both missing, and both set.
- A second test runs `calculate_case_response_cost_new` on a case whose project has both settings `NULL`.
- Without the fix they fail with the same `TypeError`. That run also reverted the earlier `min` fix, so the earlier regression test failed too.
- I also added the missing `import math` and `import pytest` at the top of the test file.

`src/dispatch/incident_cost/service.py` has an identical `get_hourly_rate` with the same bug. I left it alone because you asked about cases. It's a one-line change if you want it. You may also want to check for projects with `NULL` values and stop the project update path from writing them.

----- next turn -----

Here is the recap for the incident report.

**What happened**
- **Symptom:** from early September the finance warehouse received classic case costs several times higher than the hour before. Case 5363 went from $2,261 to $6,241 on Sep 9 when it was marked stable.
- **Root cause:** commit `20f33137` (Sep 2, "use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. Cost is meant to stop at the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, it kept accruing until the latest of them.
- **Deploy:** `main-65f7df6e` shipped it on Sep 2 at about 18:14–18:15Z. That is the first image that contains the commit, and the previous image `main-3e0445ff` doesn't. The later `main-51546e13` (Sep 4) also contains it.
- **First inflated case:** case 5284 jumped from 3331 to 8804 in the Sep 3 11:20Z sync, which was also the first `costsync.checks` warning. I checked for earlier unflagged upward jumps over $250 and found none between the deploy and that sync. The next jumps over $250 are Sep 5 (case 5327) and a batch of about $290 increases on Sep 6, which I treated as unrelated catch-up. The Sep 6 batch follows scheduler database connection failures around 03:00Z, but I didn't confirm that.
- **Ruled out:** case-cost-sync 1.5.0 (Sep 1) only changed the page size.
- **Fix:** reverted to `min`, with a regression test that sets all three timestamps. The earlier tests only set `stable_at`, which is why they missed it.
- **Second, unrelated bug:** from Sep 8 15:55Z the scheduler logged 708 hourly `TypeError`s (`None / int`). The cause was a project with `NULL` `annual_employee_cost`, which broke `get_hourly_rate`. It now falls back to the `Project` model defaults (50000 and 2080), with tests.

**Open items**
- **Warehouse backfill:** rows for cases that went stable, escalated or closed after Sep 2, 18:15Z are overstated. Rows for frozen cases won't self-correct once the fix ships.
- **Case 5363:** the Sep 5 drop from 3425 to 1243 is still unexplained.
- **Incident cost:** `incident_cost/service.py` has the same `get_hourly_rate` `NULL` bug, and I left it unfixed.
- **Project settings:** nothing yet stops a project update from writing `NULL` for these settings.
- **Not committed:** the fixes and tests are in the working tree only.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost