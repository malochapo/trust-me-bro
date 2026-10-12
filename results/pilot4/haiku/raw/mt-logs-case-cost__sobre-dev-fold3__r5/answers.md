**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py`. It changed `min(timestamps)` to `max(timestamps)`. That moves the cost cut-off for participant time from the first of stable/escalated/closed to the last. Every participant's role time on a case is then counted until the latest of those events, so costs inflate once a case has more than one of those timestamps. The code comment on that line still says "earliest relevant timestamp", so the change contradicts its own comment. Both classic and new cost models call this function.

**Deploy that shipped it:** `registry.example.com/dispatch:main-65f7df6e` on **2025-09-02**. The scheduler pod (`dispatch-scheduler-qdd74fpnsl`) started on that image at 18:15:24 UTC, and the web and DB-upgrade jobs used it too. `65f7df6e` is a descendant of `20f33137` (`git merge-base --is-ancestor` confirms it), so the fix was live from that rollout onward. The previous image was `main-3e0445ff`.

**Evidence that fits this:**
- **Timing:** the first flagged jump is on Sept 3 (case 5284). Nothing is flagged before the Sept 2 rollout. The later flags (5327, 5264, 5363, 5406) all follow it.
- **Stable-marking behavior:** the example case 5363 was 2261 from Sept 5 16:20 to Sept 9 11:20, then jumped to 6241 at 12:20, the hour it was marked Stable. Under `min`, marking a case stable can't move the cut-off if an earlier escalation already set it. Under `max`, it moves the cut-off to the later stable time. That matches the jump.
- **All six flagged cases** are Stable cases with the same warning pattern in `cost-sync.log`.

**Ruled out:**
- **cost-sync 1.4.2 → 1.5.0 (Sept 1 10:20 UTC):** it only reads case totals from Dispatch's API and copies them. The hourly deltas after the upgrade are small (about +145/hour, normal accrual), and nothing is flagged until after the Sept 2 deploy.
- **Rate or model changes:** none in the logs or the commits in the window.

**What I didn't verify:**
- I didn't reproduce the calculation, and the logs don't record `escalated_at`/`stable_at`/`closed_at` for these cases, so the per-case mechanism is inferred from the code and timing.
- Case 5363 also dropped from 3425 to 1243 on Sept 5 at 09:20, which the `max` explanation doesn't cover. I didn't resolve that.

**Suggested fix (not applied):** revert the line to `min(timestamps)` and add a regression test where a case has both an escalation and a later stable mark. The warehouse values for the affected Stable cases will need recalculating after the fix.

No code was changed.

----- next turn -----

The fix is in and the regression test is in place. The test fails on the buggy code and passes with the fix.

**Changes**
- `src/dispatch/case_cost/service.py`: `get_participant_role_time_seconds` uses `min(timestamps)` again, so the cut-off is the earliest of escalated, stable, or closed. This matches the function's existing comment.
- `tests/case_cost/test_case_cost_service.py`: new `test_case_cost_stops_at_first_cut_off_event`. It sets a case escalated 2 hours ago and marked stable 1 hour ago, with an assignee active since 3 hours ago. It expects 3600 seconds of role time (up to the escalation), not 7200. It also checks that the classic cost is calculated without error.

**Why the existing tests missed it:** `test_case_cost_stops_at_stable_time` only sets `stable_at`, so `min` and `max` give the same answer there. The new test is the first to set two cut-off timestamps.

**Verification**
- Set `max` back temporarily: the new test fails with `assert 7200.0 == 3600`. Then I restored `min`.
- `python -m pytest tests/case_cost tests/case -q`: 35 passed.

I didn't run the full test suite, only the case and case-cost tests. I also didn't deploy or recompute the warehouse values. The finance rows already inflated by the Sept 2 release will need recalculating after this fix ships.

----- next turn -----

Fixed. Projects with no annual employee cost or no business year hours now get a cost, using the model defaults. Tests cover it.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computed `project.annual_employee_cost / project.business_year_hours` with no null check. For a project where either field is NULL, Python raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler's hourly `calculate_cases_response_cost` job then fails for that case. The log has 708 of these, starting 2025-09-08 15:55. The fields are nullable in the schema, so older projects can have NULLs.

**Fix:**
- `src/dispatch/project/models.py`: the defaults 50000 and 2080 are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST` and `DEFAULT_BUSINESS_YEAR_HOURS`. The column defaults and the Pydantic fields use them, so the value lives in one place.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` substitutes the default for each field that is `None`. It checks `is None`, so an explicit 0 is not replaced; a 0 for business hours would still raise a division error. I didn't handle that case.

**Tests** (`tests/case_cost/test_case_cost_service.py`):
- `test_get_hourly_rate_uses_project_defaults_for_missing_values`: four cases covering missing cost, missing hours, both missing, and both set.
- `test_calculate_case_response_cost__project_missing_cost_fields`: an end-to-end cost calculation on a project with both fields NULL.

**Verification:** with the old `get_hourly_rate` restored, the new tests fail (4 failures). With the fix, `tests/case_cost`, `tests/case`, `tests/project` and `tests/incident_cost` pass (61 tests). I didn't run the full suite.

**Things to know:**
- Costs for those projects are now computed with the default rate of 25/hour (50000/2080). The logs don't say which projects have NULLs, so I didn't check how many cases this affects. Finance should expect those projects' figures to change once the fix ships.
- `incident_cost/service.py` has the same unguarded division in its own `get_hourly_rate`. The incident cost job will hit the same TypeError for those projects. I didn't change it because it's outside the case cost job you asked about. Say if you want it fixed the same way.
- `individual/service.py` hardcodes the same two defaults. I left it alone; it could use the new constants.

----- next turn -----

The earliest large inflated cost is the Sept 3 entry for case 5284, so FIRST_INFLATED is 2025-09-03. Smaller increases on Sept 2 would fall under my 300-unit threshold, so that date is the first large one, not a proven first. Here's the recap.

## Recap

**Cost inflation (the cost bug)**
- **Cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. Participant role time was counted until the latest of escalated, stable, or closed, not the earliest. Marking a case stable could then extend the billable window, which is why costs jumped at that point. The function's own comment said "earliest".
- **Shipped:** image `main-65f7df6e`, rolled out 2025-09-02 at about 18:15 UTC. The scheduler was on that image from 18:15:24.
- **Symptom:** the finance warehouse showed large jumps for Stable cases, for example case 5363 going from 2261 to 6241 on Sept 9. The first large jump was case 5284 on Sept 3.
- **Fix:** restored `min(timestamps)`. Added `test_case_cost_stops_at_first_cut_off_event`, which fails on the buggy code (7200 vs 3600 seconds) and passes with the fix.
- **Not verified:** I didn't reproduce the calculation or check how many warehouse rows are affected. Those rows will need recalculating.

**Hourly TypeError (separate issue)**
- **Cause:** `get_hourly_rate` divided `project.annual_employee_cost` by `project.business_year_hours` without a null check. The traceback shows `NoneType` on the left, so the missing setting is `annual_employee_cost`. The log has 708 of these, starting 2025-09-08 15:55.
- **Fix:** missing values fall back to the project model defaults, 50000 and 2080. The defaults are now named constants in `project/models.py`. Added four parametrized tests for the fallback and one end-to-end test with NULL fields. The tests fail on the old code and pass with the fix.
- **Effect:** cases in those projects now get costs at the default rate of 25/hour. Finance should expect those figures to change.
- **Not changed:** `incident_cost/service.py` has the same unguarded division, so the incident cost job can hit the same TypeError.

**Test results:** `tests/case_cost`, `tests/case`, `tests/project`, and `tests/incident_cost` pass (61 tests). I didn't run the full suite.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```