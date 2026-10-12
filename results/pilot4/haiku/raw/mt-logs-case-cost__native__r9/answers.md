**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, Sep 2) changed one character in `get_participant_role_time_seconds`, at `src/dispatch/case_cost/service.py:353`:

```python
participant_role_renounced_at = max(timestamps)   # was min(timestamps)
```

For cases past New/Triage, `timestamps` holds whichever of `stable_at`, `escalated_at` and `closed_at` are set. The cost cut-off used to be the earliest of those, which stops the clock at the first milestone. With `max`, the cut-off becomes the latest milestone. A case that was escalated and then marked Stable now accrues participant time all the way to the stable time, so the escalated-to-stable window is billed too.

The logs fit this for case 5363:
- From 9/5 16:20 to 9/9 12:20 its classic cost stays frozen at 2261. That is consistent with the cut-off sitting at the escalation time.
- At 9/9 12:20, when it was marked Stable, the cut-off moved to `stable_at` and the cost jumped to 6241.

**Deploy:** the image `registry.example.com/dispatch:main-65f7df6e` rolled out to `dispatch-web` and `dispatch-scheduler` on 2025-09-02 at 18:14–18:15 UTC, after the `dispatch-db-upgrade-65f7df6e` job. `20f33137` is an ancestor of `65f7df6e`.

The timing matches. There are no cost-sync warnings before the rollout. The first flagged jump is 2025-09-03 11:20 UTC (case 5284, 3331 → 8804), and later ones follow on 9/5, 9/8, 9/9 and 9/12, all on cases that were just marked Stable. The 9/4 rollout (`main-51546e13`) is not the cause. It only adds a `Case.canvases` relationship and does not touch cost logic, and the jumps had already started.

**Why it wasn't caught:** `tests/case_cost/test_case_cost_service.py::test_case_cost_stops_at_stable_time` sets only `stable_at`, so `min` and `max` give the same result there. Nothing tests a case with both `escalated_at` and `stable_at`. The commit message says "latest status timestamp", but the code uses the three milestone fields, not status timestamps.

**Caveats:**
- I didn't run the test suite or reproduce the numbers. The timeline inference for case 5363 assumes it was escalated before it was marked stable, because the logs contain no per-case timestamps.
- Five cases were flagged (5284, 5264, 5327, 5363, 5406), but the same mechanism probably affects every case that went escalated → stable since Sep 2. The finance warehouse will need a backfill once the fix ships.
- A separate problem: `dispatch.case_cost.scheduled` has been failing since Sep 8 with `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` at `math.ceil(project.annual_employee_cost / project.business_year_hours)`, when `annual_employee_cost` is unset. It does not explain the inflated costs, but it does mean some projects get no cost calculation.

I haven't changed any code. The likely fix is to restore `min`, or to add a test with `escalated_at` and `stable_at` set. Tell me if you want me to do either.

----- next turn -----

I restored the original `min` cut-off and added a regression test. The case_cost tests pass against the local PostgreSQL: 20 passed, up from 19.

**The fix** is in `src/dispatch/case_cost/service.py:353`: `max(timestamps)` is back to `min(timestamps)`, so cost stops at the first milestone (escalation or stable, whichever came first).

**The regression test** is `test_case_cost_stops_at_first_milestone_when_escalated_then_stable` in `tests/case_cost/test_case_cost_service.py`. It sets assumed 4h ago, escalated 3h ago and stable 1h ago, then expects 1 hour of cost. I confirmed it catches the bug: with `max` put back temporarily, it fails with 10800s (3h) instead of 3600s (1h). The fix was then restored and the suite passes.

**Things to know:**
- Ruff isn't installed here, so I didn't run the formatter. I checked by hand that the new lines are within the 100-character limit set in `pyproject.toml`.
- I ran only `tests/case_cost`, not the full suite.
- The finance warehouse still holds the inflated costs. Rows already synced since Sep 2 will stay wrong until someone backfills them, and I haven't touched that.
- The separate `annual_employee_cost` TypeError in the case_cost scheduler is still there. I left it alone because it's a different issue.

I haven't committed anything. The changes are in the working tree for you to review.

----- next turn -----

The TypeError is fixed. Cases on projects with no annual employee cost or no business year hours now get a cost, using the project model's defaults. The case_cost tests pass, 22 of 22.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Both columns are nullable, so a project with either set to NULL raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The error is raised in `calculate_case_response_cost_new`, which runs before the classic model. That means these cases lost both their new and classic costs in every hourly run. The logs show 708 such errors from Sep 8 to Sep 14. They don't say which projects have the NULLs, and I didn't find what set the values to NULL. I can only say when the errors started.

**Changes:**
- `src/dispatch/project/models.py`: added `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`, and the column defaults now use them. The values are the same as before.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` falls back to those constants when either value is `None`.
- `tests/case_cost/test_case_cost_service.py`: two new tests. One checks the rate with each value missing and with both missing. The other runs the full new-model cost calculation on a project with both values unset.

I confirmed both new tests fail with the fallback disabled, with the same `NoneType` error as production, and pass with it restored.

**Choices to know about:**
- I used the model's defaults (50000 and 2080), as you asked. The 2021 migration uses different defaults (650000 and 2080), so the two disagree.
- Only `None` triggers the fallback. A business year hours of `0` would still raise `ZeroDivisionError`. I didn't guard that, since the logs show only NULLs.
- `incident_cost/service.py` has the same `get_hourly_rate` with no fallback. The logs show no errors from it, so I left it alone. It would fail the same way if a project had NULLs.
- `individual/service.py` hardcodes 50000 and 2080 when it fills in missing values. It still works, and I didn't switch it to the constants.

Nothing is committed. The changed files are the two source files and the test file.

----- next turn -----

Here is the recap for the incident report. The six lines are at the end.

**Summary**

- **Symptom:** Since early September, the finance warehouse received case response costs several times higher than before. Case dispatch-default-security-5363 went from $2,261 to $6,241 on Sep 9, when it was marked Stable. Nobody changed the hourly rates or the cost models.
- **Root cause:** On Sep 2, commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function picks the cut-off for participant time from a case's `escalated_at`, `stable_at` and `closed_at`. The original `min` stops the clock at the first milestone. With `max`, a case that was escalated and then marked Stable kept accruing time until it was marked Stable. Finance was billed for the escalated-to-Stable window.
- **Deploy:** The image `registry.example.com/dispatch:main-65f7df6e` rolled out to `dispatch-web` and `dispatch-scheduler` on Sep 2 at 18:14–18:15 UTC. Commit `20f33137` is an ancestor of that build. The first inflated sync is Sep 3 at 11:20 UTC (case 5284, 3331 → 8804). There are no large jumps before the deploy. The image from Sep 4 (`main-51546e13`) does not touch the cost logic.
- **Why tests missed it:** The existing `test_case_cost_stops_at_stable_time` sets only `stable_at`, so `min` and `max` give the same result. No test covered a case with both `escalated_at` and `stable_at`.
- **Secondary bug:** From Sep 8, `case_cost.scheduled` logged a `TypeError` for a few cases every hour, 708 times in total. `get_hourly_rate` divided `project.annual_employee_cost` by `project.business_year_hours` without checking for NULL. The affected cases lost both their new and classic costs for those hours. The logs don't say which projects had the NULLs, and I didn't find what set them.

**Fixes (uncommitted, in the working tree)**

- `src/dispatch/case_cost/service.py`: `max` is back to `min`. `get_hourly_rate` falls back to the project defaults when either value is `None`.
- `src/dispatch/project/models.py`: the defaults (50000 and 2080) are now named constants, and the column defaults use them.
- `tests/case_cost/test_case_cost_service.py`: a regression test for escalation followed by Stable, and two tests for the unset-value fallback. I checked that the new tests fail when the fix is removed. The case_cost suite passes, 22 of 22.

**Caveats for the report**

- The fixes are not deployed. Costs already synced since Sep 2 remain wrong until the warehouse rows are backfilled.
- `FIRST_INFLATED` is based on hourly jumps over 300. A smaller inflation on the evening of Sep 2 can't be ruled out from these logs.
- `incident_cost/service.py` has the same `get_hourly_rate` without the fallback. The logs show no errors from it.
- Zero values for `business_year_hours` still raise `ZeroDivisionError`. The logs showed only NULLs, so I didn't guard that case.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```