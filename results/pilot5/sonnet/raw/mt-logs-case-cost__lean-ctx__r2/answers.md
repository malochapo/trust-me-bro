The cause is commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee). It reached production in the deploy of image `main-65f7df6e` on 2025-09-02 at 18:14Z. I confirmed the inflated rows in the logs, but not the escalation dates behind them (see the end).

**The change**
- It is a one-line edit in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`), changing `min(timestamps)` to `max(timestamps)`.
- The code builds `timestamps` from `stable_at`, `escalated_at` and `closed_at`, and the comment above it says "Determine the **earliest** relevant timestamp for cost calculation cut-off".
- The commit title says "latest", so it reversed the documented behaviour.
- A case that was escalated and later marked stable used to stop accruing cost at the escalation time. Now it keeps accruing until `stable_at` or `closed_at`.
- That adds the whole escalated-to-stable gap, at the participants' hourly rate, to the classic cost. The cost jumps the moment the case is marked stable or closed.
- Your example fits this. Case 5363 grew about $145/hour until 2025-09-05 16:20, then stayed flat at 2261 until 09-09 12:20. At that run it jumped to 6241, the sync when it showed as Stable.

**The deploy**
- Events show `dispatch-db-upgrade-65f7df6e` and a rollout of `dispatch-web-zrhzjwmzrh` and `dispatch-scheduler-qdd74fpnsl` on 2025-09-02 from 18:14Z. That image is `registry.example.com/dispatch:main-65f7df6e`.
- `20f33137` is in the range `3e0445ff..65f7df6e`. The previous production image was `main-3e0445ff`, deployed 08-27 and still running on 09-02 at 14:06Z. It contained the earlier code.
- The next deploy, `main-51546e13` on 09-04 at 16:52Z, only adds Slack canvas support. It is not the cause, because the first jump (below) came before it.
- The first flagged jump is case 5284 on 09-03 at 11:20: 3331 → 8804 (+164%). That is the first sync after the deploy that sees a case in Stable status.
- The later flags are 5327 (+147%) on 09-05, 5264 (+265%) on 09-08, 5363 (+176%) on 09-09 and 5406 (+150%) on 09-12. All are `Stable` cases.

**Not the cause**
- `case-cost-sync` moved from 1.4.2 to 1.5.0 on 09-01 at 10:20Z, and the page count went from 4 to 2. That is 8 days before the first jump, and 200 cases are read every run either way. Cost-sync's own diff and flag logging shows no problem; it faithfully copies the API values.
- The scheduler log has nothing relevant. The only messages are "No case…" lines, and none of the cases above appear in it.

**Caveats**
- The logs don't show the escalation dates, so the escalated-then-stable mechanism for 5363 is inferred from the flat cost and the code.
- The warehouse rows written since 09-02 18:14Z for cases that were stable or closed are overstated and will need correcting after a fix.

I haven't changed any code. The likely fix is to revert `max` back to `min`; say if you want that or the warehouse backfill planned.

----- next turn -----

I fixed the bug and added a regression test. With the fix, all 20 tests in `tests/case_cost` pass. With the fix stashed, the new test fails and the other 19 still pass. I didn't run the rest of the suite.

- **Fix:** In `src/dispatch/case_cost/service.py`, `get_participant_role_time_seconds` uses `min(timestamps)` again, so the cost cut-off is the earliest of `stable_at`, `escalated_at` and `closed_at`.
- **Test:** `test_case_cost_stops_at_earliest_status_time` in `tests/case_cost/test_case_cost_service.py` covers a case that was escalated, then marked stable, then closed. It asserts that the cost stops at the escalation time. The existing stable-time test only set `stable_at`, which is why it didn't catch the change.

Nothing is committed. The warehouse rows written since 2025-09-02 18:14Z for stable or closed cases are still overstated until this is deployed and finance re-syncs them.

----- next turn -----

Cases in projects with a missing annual employee cost or business year hours now get a cost instead of a TypeError. The case_cost and incident_cost tests pass (37). With the fix stashed, both new tests fail, as does the earlier regression test, which the stash also removes the fix for.

**Cause:** The `annual_employee_cost` and `business_year_hours` columns on `Project` are nullable, and the schema allows `None`. `get_hourly_rate` in `src/dispatch/case_cost/service.py` divided them without checking. For a project where either is NULL, the hourly job raised `unsupported operand type(s) for /: 'NoneType' and 'int'` inside `calculate_case_response_cost_new`.

`calculate_cases_response_cost` catches the error per case and logs it, so one bad case doesn't stop the run. That leaves 708 of these TypeErrors in `scheduler.log` since 2025-09-08 15:55, and those cases never got a cost updated.

**Not determined:** The logs don't say which projects have NULLs, or why the errors began on September 8. My guess is a project's settings were saved with empty values around then, but nothing in the logs or code confirms it. You can check with `SELECT name FROM project WHERE annual_employee_cost IS NULL OR business_year_hours IS NULL`.

**Fix:** `get_hourly_rate` now takes whichever value is missing from the `Project` column defaults, 50000 and 2080, so the rate is $25/hour for a project with neither set. It reads them from the column definitions, so they stay in sync with the model.

**Tests:** Two new tests in `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate__missing_values_use_project_defaults` checks each missing-value combination.
- `test_calculate_case_response_cost__project_without_rate_settings` runs a full cost calculation on a project with both values NULL.

**Not changed:** `get_hourly_rate` in `src/dispatch/incident_cost/service.py:133` has the same unguarded division, so incident costs for those projects will hit the same error. I left it alone since you asked about cases; say if you want it fixed the same way.

Nothing is committed.

----- next turn -----

## Recap

**Cost inflation.** On 2025-09-02, commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function sets the cut-off time at which a case stops accruing cost. The comment above it, and the earlier behaviour, call for the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, a case that was escalated and later marked stable or closed kept accruing cost for the whole gap. The inflated cost then reached the warehouse on the next hourly sync. The change shipped to production in image `main-65f7df6e`, rolled out from 2025-09-02 18:14Z.

The first inflated cost I can see is case 5284 on 2025-09-03 at 11:20Z, which went from 3331 to 8804. In the sync window between the deploy and that run, no other case rose by more than $400. A smaller inflated case in that window can't be ruled out entirely. Later flagged cases were 5327, 5264, 5363 and 5406.

**Hourly TypeError.** Since 2025-09-08 15:55, the scheduler's hourly case cost job logged 708 TypeErrors. `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`, and those project columns are nullable, so a project missing either one failed. The error handling is per case, so those cases silently got no cost update. We don't know which projects have NULLs or why it started on 09-08.

**Changes in the working tree (not committed):**
- Reverted `max` to `min`, with a regression test.
- `get_hourly_rate` now falls back to the `Project` model defaults (50000 and 2080), with tests.

**Follow-ups:**
- Backfill the warehouse rows for stable or closed cases written since 2025-09-02 18:14Z.
- The same unguarded division exists in `incident_cost/service.py`.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost or business_year_hours (the project's annual employee cost / business year hours)