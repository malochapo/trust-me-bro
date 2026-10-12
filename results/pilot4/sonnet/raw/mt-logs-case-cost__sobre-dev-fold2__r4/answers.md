Root cause: commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off", changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. I found it and the deploy from the logs and `git log`. I haven't run anything to reproduce the numbers.

**The bug** (`src/dispatch/case_cost/service.py:353`)
- The cost for a participant role runs from `assumed_at` to a cut-off. The cut-off is the earliest of `stable_at`, `escalated_at` and `closed_at`, and the role's own `renounced_at` can pull it earlier.
- The old `min()` stopped the clock the first time the case left the active state. With `max()` it stops at the latest of those timestamps.
- A case marked stable and left stable (the `Stable` cases flagged in `cost-sync.log`) keeps `closed_at` and `escalated_at` unset. Its cut-off is still `stable_at`, so its cost shouldn't change.
- When any of those timestamps is later, the cost counts hours that should have stopped. Participants without a `renounced_at` are hit hardest, because nothing else caps them.
- The code comment right below the change still says "before the case was marked as stable or closed". The commit contradicts it. It is a one-word change, and it was labelled a `fix` with no test.

**The deploy**
- The first image containing `20f33137` is `registry.example.com/dispatch:main-65f7df6e`. `65f7df6e` is the next commit on `main` after `20f33137`.
- It went to production on 2025-09-02. `events.log` shows the `dispatch-db-upgrade-65f7df6e` image pull at 18:14Z. The web pods followed at 18:14–18:15Z, and the scheduler at 18:15Z (`dispatch-scheduler-qdd74fpnsl`).
- The earlier production image, `main-3e0445ff`, went out on 2025-08-27 and has the old `min()`. The later `main-51546e13` (2025-09-04 16:53Z) just carries the bug forward.

**Timing in the logs**
- `cost-sync.log` has no flagged cost jumps before the 09-02 deploy. The first one is case 5284 on 2025-09-03 11:20Z (3331 → 8804).
- Later flags are case 5327 on 09-05, case 5264 on 09-08, case 5363 on 09-09 (2261 → 6241) and case 5406 on 09-12. All are `Stable` security cases.
- A case's cost only changes when the cost job recalculates it, so each jump lands when that case is next recomputed.

**Ruled out:** the finance job upgrade from 1.4.2 to 1.5.0 (first seen 2025-09-01T10:20Z). It did change the page size from 50 to 100. That was a day before the deploy and it doesn't touch the numbers, and no jumps appear until after 09-02.

**Cleanup after a fix:** warehouse costs for cases recomputed since 2025-09-02 18:15Z are inflated. Fixing the code won't correct them until those cases are recalculated and re-synced.

I haven't changed any code, as you asked. The fix is to revert to `min()` and add a regression test for a stable case with later `closed_at` and `escalated_at` timestamps.

----- next turn -----

I reverted `max(timestamps)` back to `min(timestamps)` in `src/dispatch/case_cost/service.py`, and added a regression test. The `tests/case_cost` suite passes (20 tests). I didn't run the rest of the suite.

The new test is `test_get_participant_role_time_seconds_uses_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. It builds a stable case whose `escalated_at` and `closed_at` are later than `stable_at`, with a role that has no `renounced_at`. It then checks that the time stops at `stable_at`. With the old `max()` code the test fails (the time ran past `stable_at`), and with the fix it passes.

I haven't committed anything. This only fixes new calculations. The warehouse rows for cases recomputed since the 2025-09-02 18:15Z deploy are still inflated until those cases are recalculated and re-synced. Finance will probably need to re-sync them.

----- next turn -----

The TypeError comes from `get_hourly_rate` in `src/dispatch/case_cost/service.py`, and I've fixed it and added a test. The `tests/case_cost` and `tests/incident_cost` suites pass (36 tests). I didn't confirm that the new test fails without the fix, though the old code would have raised the same TypeError.

**Cause**
- The scheduler log has 708 occurrences, starting 2025-09-08 15:55. The error is `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`.
- The traceback runs from `calculate_cases_response_cost` through `calculate_case_response_cost_new` into `get_hourly_rate`. That function computes `math.ceil(project.annual_employee_cost / project.business_year_hours)`.
- The traceback shows `annual_employee_cost` is `None` (`NoneType / int`). The code has no guard for either field.
- Both fields are nullable in the project schema (`annual_employee_cost: int | None` and `business_year_hours: int | None`). The column defaults of 50000 and 2080 only apply when a project is created without the field. An explicit null overrides them.
- So some project has no annual cost or no business-year hours. The logs don't name the project or say what changed on 09-08. You'll want to check the projects table.

**Fix**
- `get_hourly_rate` now falls back to the `Project` model's column default for whichever value is `None`: 50000 for the annual cost and 2080 for the hours. It reads the defaults from the model, so they stay in sync with it.
- Cases in the affected project get a cost again.
- The new test is `test_get_hourly_rate__missing_values_use_project_defaults`. It covers both values missing, only the cost missing, and only the hours missing.

**Still open**
- `incident_cost/service.py` has an identical `get_hourly_rate` with the same crash. I left it alone because you asked about the case job, but it's an easy follow-up.
- The error handling in `calculate_cases_response_cost` may also be worth a look. If the `try`/`except` wraps the whole loop, one bad case would skip the cases after it each hour. I didn't confirm that.

Nothing is committed.

----- next turn -----

The root cause is a one-word change in the cost cut-off logic. It made stable cases keep accruing cost after they were marked stable. A separate bug in the hourly-rate code was crashing the scheduler's cost job for some cases.

**Cost inflation**
- **Cause:** commit `20f33137` ("use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. A role's cost is meant to stop at the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max()` it ran to the latest instead.
- **Deploy:** the first image containing that commit is `registry.example.com/dispatch:main-65f7df6e`. It went to production on 2025-09-02 at about 18:14–18:15Z. `events.log` shows the db-upgrade pod, then the web pods, then the scheduler pod all pulling that image. The next image, `main-51546e13` (2025-09-04), carries the bug forward.
- **First inflated case:** case 5284, flagged in `cost-sync.log` at 2025-09-03T11:20Z (classic cost 3331 → 8804). Smaller inflations before that can't be separated from normal growth of active cases, because the sync log carries no case status. Other flagged cases are 5327 (09-05), 5264 (09-08), 5363 (09-09) and 5406 (09-12).
- **Fix:** reverted to `min()`, plus a regression test. Warehouse rows already inflated still need those cases recalculated and re-synced.

**Hourly TypeError (since 2025-09-08)**
- **Cause:** `get_hourly_rate` divides `project.annual_employee_cost` by `project.business_year_hours`. The traceback says `NoneType / int`, so the numerator is `None`: a project has no annual employee cost set. Only the numerator can be `None` in that message.
- **Why the project's value is `None`:** the logs don't say. The model's default of 50000 only applies when the field isn't supplied at creation, and both settings accept an explicit null.
- **Fix:** it now falls back to the `Project` model defaults (50000 annual cost, 2080 hours) when either value is missing, plus a test.
- **Still open:** the identical `get_hourly_rate` in `incident_cost/service.py` has the same bug. I haven't checked whether the scheduler loop skips the remaining cases after one fails.

Both fixes and both tests are uncommitted in the working tree. The `tests/case_cost` and `tests/incident_cost` suites pass.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost