The root cause is commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, 2025-09-02). It reached production in the `main-65f7df6e` deploy on 2025-09-02 at about 18:14–18:15Z.

**The change**

In `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`), the cost cut-off changed from `min(timestamps)` to `max(timestamps)`. The timestamps are `stable_at`, `escalated_at` and `closed_at`. The comment right above it still says "earliest relevant timestamp", and the code below still says "before the case was marked as stable or closed". Every participant's time in a role is measured up to that cut-off. When a case has more than one of those timestamps, the cut-off now moves to the latest one, so the billed time and cost go up. Nobody touched the rates or cost models, which matches what you saw.

**Why `main-65f7df6e` is the deploy**

- `20f33137` is an ancestor of `65f7df6e`, and the commit is dated 09:29 PDT on 2025-09-02, before that deploy.
- The earlier production images, `main-b01a1aba` and `main-3e0445ff` (rolled out 2025-08-27), predate the commit.
- In `events.log`, `main-65f7df6e` shows up at 2025-09-02T18:14Z. The db-upgrade job, web pods and then the scheduler pods all roll to it, and the scheduler is what recalculates costs hourly. The later `main-51546e13` deploy (2025-09-04T16:52Z) also contains the commit, but it wasn't the first.
- `cost-sync.log` has 499 runs with "0 flagged" and 5 with 1 flagged. All five flagged +147% to +265% jumps come after the 09-02 deploy:
  - case 5284 on 09-03
  - case 5327 on 09-05
  - case 5264 on 09-08
  - case 5363 on 09-09
  - one more, in the run ending the flagged list
- All the flagged cases are Stable security cases, and case 5363 jumped from $2,261 to $6,241 when it was marked stable.

**What I could not confirm**

- The logs don't show each case's `stable_at`, `escalated_at` or `closed_at` values. I can't say which timestamp pushed each case's cut-off later. I also can't say why the jumps cluster on Stable cases. One likely reason is that the scheduler recalculates a case once after it goes stable and then stops.
- The jump size depends on how far apart the timestamps are. A case with only `stable_at` set gets the same cut-off from `min` and `max`.
- I can't tell how many of the other changed cases were affected. My first awk filter for large jumps was broken, so I didn't get a clean count. Only the flagged jumps are certain.

**A confounder I ruled out**

`case-cost-sync` itself was upgraded from 1.4.2 to 1.5.0 on 2025-09-01 at about 10:20Z. That is before the Dispatch deploy, and nothing was flagged until after 09-02, so the timing points to the Dispatch change, not the finance job. I haven't seen the 1.5.0 changelog.

**Next steps**

Per your instruction I haven't changed any code. To fix it, revert `20f33137` (or restore `min`) and deploy. After that, the stored costs need recomputing for the affected cases, mainly Stable ones since 2025-09-02. The warehouse will also need a re-sync for those cases, because the scheduler skips stable cases it has already updated.

----- next turn -----

I've restored the `min(timestamps)` cut-off in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py`). I also added a regression test. Nothing is committed or deployed yet.

**Test:** `test_case_cost_stops_at_earliest_status_timestamp` is in `tests/case_cost/test_case_cost_service.py`. It builds a closed case with `stable_at`, `escalated_at` and `closed_at` at different times, and checks that a participant's time stops at the earliest one. The existing stable-time test only set `stable_at`, which is why it never caught the change.

**Results:** The new test fails with the fix removed and passes with it. All 20 tests in `tests/case_cost` pass with the fix. I didn't run the rest of the suite.

**Still to do:**
- Commit and deploy the fix.
- Recompute the stored costs for cases affected since 2025-09-02. The scheduler skips stable cases it has already updated after `stable_at`, so those cases won't correct themselves.
- Ask the finance team to re-sync those cases into the warehouse.

I can do the commit if you want.

----- next turn -----

I fixed the TypeError: the hourly case cost job now falls back to the Project model's defaults for any missing rate input. I added a test for it, and the case_cost, incident_cost and project tests pass (42 tests). Nothing is committed or deployed.

**Cause**
- Every error is `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` in `get_hourly_rate` (`src/dispatch/case_cost/service.py`). It divides `project.annual_employee_cost` by `project.business_year_hours`, and one of the two is `None` for the affected project.
- The columns have a default (50000 and 2080), but that only applies when a project is inserted. `ProjectBase` allows `None` for both fields. `project.service.update` copies whatever the API sends onto the project, so a project updated with null values stores NULL.
- `get_hourly_rate` assumed the values were always set.
- Each error comes from the "new" cost model path (`calculate_case_response_cost_new`). The exception is caught per case in `calculate_cases_response_cost`, so those cases are skipped each hour and keep a stale cost.
- The logs have 708 of these TypeErrors. I couldn't see which project it is, or exactly what set the NULLs, because the database isn't in the logs.
- Of the three logs, only `scheduler.log` has a TypeError. The first one is dated 2025-09-08, and there are no other ERROR lines except an unrelated database "connection refused" burst on 09-06.

**Fix**
- `get_hourly_rate` now uses the Project column default for whichever value is `None` (`Project.__table__.c.<col>.default.arg`), so the defaults live in one place.
- The new test is `test_get_hourly_rate__missing_values_use_project_defaults` in `tests/case_cost/test_case_cost_service.py`. It covers both values missing, only one missing, and checks the resulting rates.

**Not changed**
- `incident_cost/service.py:131` has an identical `get_hourly_rate` with the same bug, and no TypeError appears in these logs for it. You asked only about cases, so I left it alone. I can apply the same fix there.
- The NULLs can still be written. The real fix is to reject null in the project update API or stop `update` writing None, but that changes API behaviour, so it's your call.
- Affected cases will correct themselves on the next hourly run after deploy. Their costs have been stale since 09-08, so finance should expect a catch-up change for them.

----- next turn -----

## Recap

**Inflated costs.** Since the `main-65f7df6e` deploy on 2025-09-02 (about 18:14–18:15Z), case costs have been calculated up to the wrong end time. Commit `20f33137` changed the cut-off for a participant's time in `get_participant_role_time_seconds` from `min(timestamps)` to `max(timestamps)`. The timestamps are `stable_at`, `escalated_at` and `closed_at`. With more than one set, the later one was used, so the billed time went up. The rates and cost models were never touched.

**Evidence.**
- Before the deploy, no case's hourly change in `cost-sync.log` exceeded $221.
- After it, five jumps of $2,970–$8,702 appear: cases 5284, 5327, 5264, 5363 and 5406. Case 5363 went from $2,261 to $6,241 on 09-09.
- The first of them, case 5284 at 2025-09-03 11:20Z (+$5,473), gives the FIRST_INFLATED date.
- I scanned the diff lines for the gap between the deploy and that jump, and found only ordinary growth (about $194–$230/hour on case 5323).
- I can't see each case's status timestamps in the logs, so the mechanism is inferred from the code.

**Fix.** `min(timestamps)` is restored in `get_participant_role_time_seconds`, with a regression test, `test_case_cost_stops_at_earliest_status_timestamp`. It fails without the fix and passes with it.

**Clean-up still needed.** Stored costs for cases affected since 2025-09-02 must be recomputed, and finance needs to re-sync them. The scheduler skips stable cases it has already updated.

**Hourly TypeError.**
- **Cause:** `get_hourly_rate` divides the project's annual employee cost by its business-year hours. For one project the cost was `None`, so the division failed.
- **How NULL got in:** the project update API accepts null, and the column default only applies on insert.
- **Impact:** about 708 errors in `scheduler.log`, the first dated 2025-09-08. Each skipped the affected case's cost update every hour.
- **Fix:** the function now falls back to the Project model's defaults (50000 and 2080), with a test. Cases update on the next hourly run after deploy.
- **Still open:** `incident_cost/service.py` has the identical flaw, and the API can still write NULL.

**Status.** Both fixes and both tests are in the working tree, uncommitted and undeployed. `tests/case_cost`, `tests/incident_cost` and `tests/project` pass. I haven't run the rest of the suite.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost