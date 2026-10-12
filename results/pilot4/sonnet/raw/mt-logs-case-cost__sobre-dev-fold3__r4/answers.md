**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02) changed one line in `get_participant_role_time_seconds()` in `src/dispatch/case_cost/service.py`. It changed `min(timestamps)` to `max(timestamps)`.

- **Before:** the cost of a participant's role stopped at the earliest of `stable_at`, `escalated_at` and `closed_at`. A case that went stable stopped accruing at that point. The code comment still says "earliest relevant timestamp".
- **After:** the cut-off is the latest of those timestamps. Any case with more than one of them set keeps accruing up to the later one. The cost is no longer bounded by the moment the case became stable, so it jumps.

**Shipped by:** the deploy of image `registry.example.com/dispatch:main-65f7df6e` on 2025-09-02. The events log shows the db-upgrade job at 18:14:09Z, the web pod at 18:14:37Z and the scheduler pod at 18:15:10Z. That build is the first to contain `20f33137`, and the cost calculation runs in the scheduler. The two other deploys in the window don't fit:

- `main-3e0445ff` (2025-08-27) predates the change.
- `main-51546e13` (2025-09-04) came after the first inflated cost (see below).

**Evidence from the logs:**
- cost-sync flags a cost jump over 100% five times, all after that deploy and none before: 09-03, 09-05, 09-08, 09-09 and 09-12. The first is case 5284 on 2025-09-03 at 11:20Z, 3331 → 8804.
- Case 5363 grew by about $145 an hour, then froze at $2,261 at 2025-09-05 16:20Z. At 2025-09-09 12:20Z it jumped to $6,241. That fits a later timestamp (a close or escalation) being set after `stable_at`, with `max()` extending the cut-off to it. I couldn't see which timestamp changed, because the logs only carry costs.
- The cost-sync job went from 1.4.2 to 1.5.0 on 2025-09-01, before the first jump, and it only copies what the API returns. I didn't see anything in its logs that would inflate costs. Hourly rates and cost models are unchanged, as you said.

**Unrelated error:** from 2025-09-08 the scheduler logs 708 `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` in `get_hourly_rate`. That is `project.business_year_hours` being `None`. It started on a different date and has a different symptom (missing costs, not inflated ones), and I didn't investigate it further.

**Still to do:**
- I haven't confirmed in the database which timestamp moved for 5363. I also haven't checked whether the commit's intent (cost until close) was a deliberate product decision. The `min` behaviour looks like what finance expected.
- Fixing the code isn't enough. Costs already recomputed since 2025-09-02 will need recalculating, and the warehouse rows rewritten, for affected cases.

No code was changed.

----- next turn -----

I reverted the one-line change in `src/dispatch/case_cost/service.py`: the cut-off is the earliest of `stable_at`, `escalated_at` and `closed_at` again (`max(timestamps)` back to `min(timestamps)`).

I also added `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. It sets a closed case with `stable_at`, `escalated_at` and `closed_at` all at different times, and expects the role time to stop at `stable_at`. With the fix, all 20 case_cost tests pass. With the fix stashed, only the new test fails and the other 19 pass, so it would have caught the regression. The existing stable-time test missed it because it only set `stable_at`.

Nothing is committed or deployed. Two things remain:
- **Deploy:** the fix has to ship before new inflated costs stop appearing.
- **Backfill:** costs recomputed since the 2025-09-02 deploy of `main-65f7df6e` are still wrong. Affected cases need their costs recalculated, and the warehouse rows corrected. I haven't done either.

I didn't touch the separate `business_year_hours` is `None` TypeError in the scheduler.

----- next turn -----

The TypeError comes from a project with a NULL `annual_employee_cost`, and the fix makes those cases get a cost using the project defaults. The case_cost and project tests pass (27), but I didn't run the new test against the old code to confirm it fails there.

**Cause:** `get_hourly_rate()` in `src/dispatch/case_cost/service.py` computed `project.annual_employee_cost / project.business_year_hours` with no None handling. The error is `'NoneType' and 'int'`, so the left operand, `annual_employee_cost`, was None. In my earlier summary I said `business_year_hours` was the None one, and that was wrong. Both columns are nullable, and the project schema allows `None`. The scheduler job `calculate_cases_response_cost` catches the error per case, so the same cases failed every hour from 2025-09-08 and got no updated cost. Only the cost-model path is affected (it fails in `calculate_case_response_cost_new`).

**Fix:** `get_hourly_rate()` now substitutes the column default (50000 for annual cost, 2080 for business-year hours) for whichever value is None. It reads the default from the `Project` model rather than hard-coding it. `src/dispatch/individual/service.py` already did the same fallback for the same two fields.

**Test:** `test_get_hourly_rate__missing_values_use_project_defaults` covers both values missing, only the annual cost missing, and only the business-year hours missing.

**Not done:**
- **Why Sep 8:** the logs don't say what produced the NULL on that date. My guess is a project was created or edited around then with the field blank, but I haven't confirmed it. Checking `project.annual_employee_cost IS NULL` in the database would show it.
- **`incident_cost`:** `src/dispatch/incident_cost/service.py` has an identical `get_hourly_rate()` with the same flaw. I left it alone because you asked about cases.
- **Commits:** nothing is committed. The working tree also still holds the earlier `min()` fix and its test.

----- next turn -----

## Recap

**The cost bug.** Commit `20f33137` (2025-09-02) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`. The cost cut-off for a case is the earliest of `stable_at`, `escalated_at` and `closed_at`. After the change, a later escalation or close moved the cut-off forward and added the idle time after the case went stable. Costs jumped when that later timestamp was set, as with case 5363 ($2,261 to $6,241 on 2025-09-09).

**The deploy.** Image `main-65f7df6e` rolled out on 2025-09-02 at about 18:14Z (db-upgrade, then web, then scheduler). It was the first build containing `20f33137`. The earlier `main-3e0445ff` build predates the commit. `main-51546e13` (2025-09-04) came after the first inflated cost.

**First inflated cost.** I scanned every cost increase in cost-sync.log. Only five are large: 2025-09-03, 09-05, 09-08, 09-09 and 09-12. The first is case 5284 on 2025-09-03, 3331 to 8804. Nothing before the deploy looks like it, so smaller inflated costs earlier on 2025-09-02 or 2025-09-03 are unlikely, though I can't fully rule them out from cost deltas alone.

**The TypeError.** Since 2025-09-08 the hourly scheduler job hit `None / int` in `get_hourly_rate()`. A project had no `annual_employee_cost`, the left operand. In my first recap I wrongly blamed `business_year_hours`. I don't know why it started on 09-08, because the logs don't show a project edit.

**Changes made.** Neither is committed:
- Restored `min()` in `get_participant_role_time_seconds()`. The new test `test_case_cost_stops_at_earliest_status_timestamp` fails on the old code and passes with the fix.
- `get_hourly_rate()` now falls back to the project model defaults (50000 and 2080) for a missing value. The new test `test_get_hourly_rate__missing_values_use_project_defaults` covers it. I didn't confirm this one fails on the old code.

**Still to do:**
- Deploy both fixes.
- Recalculate costs inflated since 2025-09-02 and correct the warehouse rows.
- Check which project has the NULL `annual_employee_cost`.
- Apply the same None fallback to `incident_cost`, which has the same flaw.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost