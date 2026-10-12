**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, 2025-09-02) changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py:353`:

```diff
-            participant_role_renounced_at = min(timestamps)
+            participant_role_renounced_at = max(timestamps)
```

The function picks a cut-off from the case's `stable_at`, `escalated_at` and `closed_at`. With `min`, cost stopped at the first of those. With `max`, it runs to the last one. So any case that was escalated (or closed) before it was marked stable now accrues cost for the whole gap between those events. Hourly rates and cost models are untouched, which matches what finance sees.

**Deploy that shipped it:** `registry.example.com/dispatch:main-65f7df6e`, rolled out to production on 2025-09-02 at 18:14–18:15 UTC (`events.log`, dispatch-db-upgrade-65f7df6e and dispatch-scheduler-qdd74fpnsl; the scheduler pulled the image at 18:15:10). `20f33137` is an ancestor of that commit. The scheduler stayed on that image until 2025-09-04 16:53, when `main-51546e13` replaced it.

**Timing evidence:**
- No case in `cost-sync.log` had a >100% jump before the 09-02 deploy. The first flagged one is case 5284 on 09-03 11:20 (3331 → 8804).
- Changed-case counts per day in `cost-sync.log` don't show a clean step. They do show a shift in which cases change: after the deploy, cases that were stable or escalated pick up growing costs. That's consistent with the mechanism, but I couldn't confirm it per case.
- Case 5363 fits the pattern: its cost rose from 131 on 09-04 to 2116 on 09-05 while it was not yet stable. The jump to 6241 on 09-09 came when it was marked stable, which is when a stable/escalated gap starts counting.

**Why tests missed it:** `tests/case_cost/test_case_cost_service.py` (`test_case_cost_stops_at_stable_time`) covers only the `stable_at` case. Nothing covers mixed timestamps, where `min` and `max` differ.

**Open question for you to decide (I haven't changed anything):** the commit title calls this a fix, but the surrounding code says otherwise. The docstring comment still reads "Determine the earliest relevant timestamp for cost calculation cut-off", and the `renounced_at` branch says "if it happened before the case was marked as stable or closed", both of which assume the earliest timestamp. So the intent is ambiguous. The fix is either to revert to `min`, or to decide that cost should run to the last status change and update the comments and tests to match. Jordan Lee would be the one to ask about the intent.

**Separate issues I noticed but did not trace:**
- `get_hourly_rate` raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` on `project.annual_employee_cost` being None. It shows up on 09-06 and 09-08 in `scheduler.log`. It's a different problem from the cost increase, but it means some cases fail to update at all.
- `cost-sync.log` changes from `case-cost-sync 1.4.2` to `1.5.0` on 09-09. That is after the increase began, so it doesn't explain it, but finance may want to check the change.

----- next turn -----

The fix is in and the regression test is in place. I did not commit; the changes are in the working tree.

**The fix:** `src/dispatch/case_cost/service.py:353` changes `max(timestamps)` back to `min(timestamps)`. Cost now stops at the earliest of `stable_at`, `escalated_at` and `closed_at`, as the function's comment says. I took "fix it" to mean reverting to that behavior. The commit title called the `max` change a fix, so if the team actually wanted cost to run to the last status change, the comment and this test would need to change together. Jordan Lee would know which was intended.

**The regression test:** `test_case_cost_stops_at_first_status_change` in `tests/case_cost/test_case_cost_service.py`. The case is escalated 2 hours ago and marked stable 1 hour ago, and the assignee was assigned 3 hours ago. The expected role time is 1 hour, ending at escalation. The old `max` code gives 2 hours.

**Verification:**
- `python -m pytest tests/case_cost`: 20 passed, with the fix applied.
- With `max` put back temporarily, the new test fails. I then restored `min`.
- I ran only the case-cost suite, not the full test suite.

----- next turn -----

Fixed. Projects with a NULL `annual_employee_cost` or `business_year_hours` now fall back to the project model's defaults (50000 and 2080) instead of raising.

**Cause:** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` with no check. The model's `default=` only applies when a row is inserted, so projects whose stored values are NULL stay NULL. Every hour, the `TypeError` aborts the cost update for each case in such a project. The scheduler log has 708 of these errors from 2025-09-08 15:55 through 09-14, all from `dispatch.case_cost.scheduled`. The logs don't name the projects, so I haven't confirmed which projects have NULLs or how they got that way. No commit in the production range touched project defaults, but I only checked the cost and participant paths, so the source of the NULLs is still open.

**Changes:**
- `src/dispatch/project/models.py`: the defaults become named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and `ProjectBase` use them, so the values live in one place.
- `src/dispatch/case_cost/service.py` and `src/dispatch/incident_cost/service.py`: `get_hourly_rate` substitutes each default independently when its field is `None`. I also fixed `incident_cost`, which has the identical unguarded function. You only asked about the case cost job, so say if you'd rather that be a separate change.

**Tests** (in `tests/case_cost/test_case_cost_service.py`):
- `test_get_hourly_rate_uses_project_defaults_when_missing` covers both fields NULL, only cost NULL, and only hours NULL.
- `test_calculate_case_response_cost_new_with_missing_project_values` runs the new-model calculation on a project with both fields NULL, which is the path that raised in production.

Both fail on the old code with the production `TypeError` and pass with the fix. I restored the fixed file afterwards.

**Verification:** `python -m pytest tests/case_cost tests/incident_cost tests/project` gives 43 passed. I didn't run the full suite. `ruff` isn't installed here, so I didn't run lint or format checks.

The changes are uncommitted in the working tree. The test file changed on disk once during this session; its contents matched my edits, so I left it as is.

----- next turn -----

Here's the recap for the incident report. Nothing is committed or deployed yet.

**Incident: inflated case response costs**

- **Cause:** On 2025-09-02, commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function sets where a participant's time stops counting. The earliest of `stable_at`, `escalated_at` and `closed_at` is the correct cut-off, and the function's own comments say so. With `max`, cost ran to the latest of those events, so a case that was escalated and later marked stable kept accruing cost between the two. Rates and cost models were unchanged.
- **Shipped:** the `main-65f7df6e` image, rolled out to production on 2025-09-02 at about 18:15 UTC. The scheduler ran it until 2025-09-04, when `main-51546e13` replaced it.
- **Evidence:** the first flagged jump was case 5284 on 09-03, from 3331 to 8804. Case 5363 went from 2261 to 6241 on 09-09, when it was marked stable. The logs can't show the first inflated cost to the hour, so FIRST_INFLATED uses the first flagged jump. Inflation may have started on the evening of 09-02.
- **Fix:** `min` is restored. Regression test: `test_case_cost_stops_at_first_status_change`. It fails with `max` and passes with `min`.

**Separate issue: hourly TypeError (708 errors, 2025-09-08 to 09-14)**

- **Cause:** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` without checking for NULL. The model's `default=` applies only on insert, so projects with NULL values stayed NULL and their cases were skipped every hour.
- **Fix:** both values fall back to the model defaults, 50000 and 2080, which are now named constants in `project/models.py`. The same fix covers the identical function in `incident_cost`. Tests: `test_get_hourly_rate_uses_project_defaults_when_missing` and `test_calculate_case_response_cost_new_with_missing_project_values`. Both fail on the old code and pass now.
- **Open:** the logs don't name the affected projects, and I haven't found how their settings became NULL.

**Verification:** `python -m pytest tests/case_cost tests/incident_cost tests/project` gives 43 passed. I didn't run the full suite, and `ruff` isn't installed here.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost