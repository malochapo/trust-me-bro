**Root cause:** commit `20f33137` (Jordan Lee, Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed one line in `src/dispatch/case_cost/service.py:353`, `min(timestamps)` → `max(timestamps)`. The function computes the cut-off at which a participant's time in a role stops accruing. It collects the case's `stable_at`, `escalated_at` and `closed_at`. The original `min` stops accrual at the earliest of these, which matches the function's own comment ("the earliest relevant timestamp"). `max` stops it at the latest, so a case that was escalated and later marked stable keeps accruing cost for the whole escalated→stable interval.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`, rolled out to the scheduler at **2025-09-02 18:15 UTC** (`events.log` lines 2089–2108). `65f7df6e` is a descendant of `20f33137`, and the previous scheduler image (`main-3e0445ff`, Aug 27) predates it. The scheduler stayed on images containing this change until Sep 4, when it moved to `main-51546e13`, which also contains it. The bug is still in HEAD.

**Why it shows up as a jump at "marked stable":** the scheduler (`scheduled.py`) recomputes a stable case's cost only once, when the stored cost is older than `stable_at`. While the case was escalated, the cut-off was `escalated_at` under both versions. When it's marked stable, `min` still gives `escalated_at`, so nothing changes. `max` gives `stable_at`, so the cost jumps by the escalated→stable interval, and then freezes. That matches case 5363 going from $2,261 to $6,241 on Sep 9 with no rate or model change.

**Evidence from the logs:**
- The first WARNING for a stable-case jump is Sep 3 (case 5284, 3,331 → 8,804). Later ones: Sep 5, Sep 8 (5264, 3,285 → 11,987), Sep 9 (5363), Sep 12 (5406). All are after the Sep 2 18:15 rollout.
- Before that, cost-sync shows only normal hourly growth on active cases.

**Ruled out:**
- **cost-sync 1.5.0 (Sep 1):** it changed the page size from 50 to 100 and does not touch cost arithmetic. The diffs were already in normal range before the deploy.
- **Scheduler `TypeError`** (708 tracebacks, `get_hourly_rate` dividing by `business_year_hours`, which is `None`): this is a separate data/config problem, not the source of the inflation. It's worth a ticket of its own.

**Test gap:** `tests/case_cost/test_case_cost_service.py` (around line 358) only sets `stable_at` on its own. Nothing tests `escalated_at` and `stable_at` together, so the change passed CI.

**Caveat:** I had no database access, so I couldn't read case 5363's row. The mechanism is inferred from the code and from the timing of the jumps. Confirming it would mean checking that case's `escalated_at` is before its `stable_at`. I haven't changed any code.

----- next turn -----

The fix is in and the regression test catches the bug. I haven't committed.

**Fix:** `src/dispatch/case_cost/service.py:353` changes `max(timestamps)` back to `min(timestamps)`. The cut-off is again the earliest of `stable_at`, `escalated_at` and `closed_at`, which is what the function's comment describes and what the code did before commit `20f33137`.

**Regression test:** `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. The case is escalated two hours in, then marked stable one hour in. The test checks that the role time stops at `escalated_at`, both while stable and after the case is closed later. The existing stable-time test only sets `stable_at`, which is why the change passed CI.

**Verification:**
- Before the fix, the new test failed with `7200.0 == 3600`: the cost ran to `stable_at` instead of `escalated_at`.
- After the fix, `tests/case_cost` and `tests/incident_cost` pass (35 tests).
- The full `python -m pytest` run gives 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I stashed my changes and reran those 8 on the unmodified commit, and they fail the same way, so they predate this work and I left them alone.

**Still open:**
- The fix only reaches production once it's deployed. The scheduler is currently on `main-51546e13`, which contains the bug.
- Existing bad costs stay inflated. Stable cases that were recalculated after Sep 2 keep their inflated values, because the scheduler only recomputes a stable case when its stored cost predates `stable_at`. Correcting them needs a backfill, which I haven't designed or run.
- The unrelated `business_year_hours is None` `TypeError` in the scheduler is still there.

----- next turn -----

The `TypeError` is fixed, and cases on projects with unset values now get a cost. I have not committed.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Both columns are nullable, and the API schema (`ProjectBase`) accepts `None`. The SQLAlchemy `default=` only applies when no value is supplied, so a project saved with an explicit NULL keeps it. The division then raises `unsupported operand type(s) for /: 'NoneType' and 'int'`. The per-case `try/except` in `calculate_cases_response_cost` catches it, logs it, and skips that case, so it never gets a cost. The logs don't name the affected projects, so I can't say which project was saved with NULL or when.

**Fix:** `get_hourly_rate` now falls back to the project model's defaults when a value is `None`: 50000 per year for cost and 2080 hours for business year. These are the values in `src/dispatch/project/models.py`, and they match the fallback already in `individual/service.py`. I did not use the 650000/2000 values in the old migration.

**Tests** in `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate_falls_back_to_project_defaults` is parametrized over each missing value and both missing, and checks the rate is `ceil(50000 / 2080)`.
- `test_case_cost_with_unset_project_values` checks that a case on such a project gets a nonzero classic cost at the default rate.

I did not check that the new tests fail on the unmodified code. Without the fallback, the `None` inputs raise the same `TypeError` the logs show.

**Verification:** the case-cost tests pass (24). The full suite gives 364 passed, 4 skipped, and the same 8 failures as before. Those 8 also fail on the unmodified commit, so they predate this work.

**Left alone:**
- `src/dispatch/incident_cost/service.py:133` has the same `get_hourly_rate` with the same bug. Incident costs would hit the same error on those projects. I didn't change it because you asked about the case cost job. Say if you want it fixed too.
- A `business_year_hours` of 0 still raises `ZeroDivisionError`. I only handled `None`, since 0 isn't a value the model defaults cover. Say if you want 0 treated as missing as well.
- Cases that failed since Sep 8 are still uncosted. They'll be picked up on the next hourly run after this is deployed.

----- next turn -----

The recap is below. The six lines at the end are the values you asked for. `FIRST_INFLATED` is the first inflated value in the cost-sync log, which I checked against every diff from the deploy onward. The Dispatch database itself has no timestamps I could check, so an earlier inflation can't be ruled out.

## Recap

**Cost bug.** Commit `20f33137` (Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The function picks the time at which a participant's role stops accruing cost, from `stable_at`, `escalated_at` and `closed_at`. The original `min` stops at the earliest of these, which matches the function's comment. `max` stops at the latest, so a case that was escalated and later marked stable kept accruing cost for the escalated→stable interval. The scheduler recalculates a stable case once it becomes stable, so the jump appears at that point. Case 5363 went from $2,261 to $6,241 on Sep 9 this way.
- Shipped in `main-65f7df6e`, rolled out to the scheduler on Sep 2 at 18:15 UTC. The scheduler has run images containing this change since then, including the current `main-51546e13`.
- Fix: `min` restored. Regression test `test_case_cost_stops_at_earliest_status_timestamp` fails on the buggy code (7200 vs 3600 seconds) and passes after the fix.

**Hourly TypeError.** Since Sep 8, the hourly job has logged `unsupported operand type(s) for /: 'NoneType' and 'int'` for some cases. `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. A project saved with NULL for `annual_employee_cost` made the numerator `None`. The per-case handler skipped those cases, so they never got a cost.
- Fix: a missing value now falls back to the project model defaults, 50000 and 2080. Tests `test_get_hourly_rate_falls_back_to_project_defaults` and `test_case_cost_with_unset_project_values` cover this.
- I could not identify which project was saved with NULL from the logs.

**Test results.** The full suite gives 364 passed, 4 skipped, and 8 failures in `tests/ai`, `tests/database` and `tests/entity`. The same 8 fail on the unmodified commit.

**Not done:**
- Nothing is committed or deployed yet.
- Stable cases already inflated since Sep 2 keep their wrong values until someone backfills them. I haven't designed or run that.
- `src/dispatch/incident_cost/service.py` has the same `get_hourly_rate` without the fallback.
- A `business_year_hours` of 0 still raises `ZeroDivisionError`.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost