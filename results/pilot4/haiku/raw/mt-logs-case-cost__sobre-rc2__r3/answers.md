**Root cause:** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds` (`src/dispatch/case_cost/service.py:353`). That function sets the cut-off for role time. It takes the stable, escalated and closed timestamps, and the code comment above it says "earliest relevant timestamp". With `max`, the cut-off becomes the latest milestone instead of the first.

**How it produces the jump:**
- The hourly job does not recompute escalated cases, so a case's cost freezes when it escalates.
- When that case is later marked Stable, the job recomputes it. With `min`, the cut-off stayed at the escalation time, so the cost did not move. With `max`, the cut-off moves to the stable time, and all the time between escalation and stable is billed at once.
- Stable cases are then frozen after one recompute, so the inflated number sticks.

**Evidence:**
- Case 5363 accrues about +145 per hour from 2025-09-04 to 2025-09-05 16:20 (2261). It then stays flat for about 3.8 days and jumps to 6241 at 2025-09-09 12:20, which matches the escalate-then-stable pattern. I can't confirm the escalation timestamp from these logs, since there is no database access, so that link is inference.
- Five cases show this one-step jump, all after the deploy: 5284 (3331→8804, Sep 3), 5327 (2244→5539, Sep 5), 5264 (3285→11987, Sep 8), 5363 (2261→6241, Sep 9), 5406 (1975→4945, Sep 12).

**The deploy:**
- Commit `20f33137` (2025-09-02 09:29 -0700) is an ancestor of `65f7df6e`, which is the image `registry.example.com/dispatch:main-65f7df6e`.
- That image was pulled on 2025-09-02 at 18:14Z for web, scheduler and the DB upgrade job. The scheduler restarted on it at 18:15:30Z.
- The first flagged jump is 2025-09-03 11:20Z, the first hourly sync after that restart.
- The later deploy `main-51546e13` (2025-09-04 16:52Z) does not change this, since it contains `65f7df6e` and the bug is already present.

The commit message says "latest status timestamp", but the code comment says "earliest". That mismatch is probably how the change got through review.

**Notes for the fix (not applied, as you asked):**
- Restoring `min` should fix new recomputations.
- Costs already inflated will stay inflated, because stable cases are skipped after one recompute. Those five cases, and any others that escalated and then went stable after the deploy, will need a targeted recalculation before the finance warehouse is corrected.

I made no code changes.

----- next turn -----

The fix is in, with a regression test, and it's uncommitted in the working tree. I didn't commit because you didn't ask for one.

**Fix:** `src/dispatch/case_cost/service.py:353` goes back to `min(timestamps)`. This restores the pre-`20f33137` blob exactly, and it matches the function's comment ("earliest relevant timestamp").

**Regression test:** `test_get_participant_role_time_seconds__stops_at_first_milestone` in `tests/case_cost/test_case_cost_service.py`. It builds a stable case that escalated an hour before it was marked stable, and asserts role time stops at escalation. I confirmed it fails with `max` and passes with `min`.

**Test results:**
- `tests/case_cost`: 20 passed.
- Full suite: 360 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They also fail on the untouched code, so they predate this change. I didn't investigate them.

**Not done:**
- Costs already inflated by the bug aren't corrected. Stable cases are skipped after their first recompute, so the five affected cases (5284, 5327, 5264, 5363, 5406) and any others that escalated and then went stable since 2025-09-02 need a targeted recalculation before the finance warehouse is right.
- The test file changed on disk during my session. The content matched what I had appended, so I kept it.

----- next turn -----

The TypeError is fixed and covered by tests. Projects with no annual employee cost or no business year hours now get a case cost, using the model defaults of 50,000 and 2,080. The changes are uncommitted.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. When either is NULL, Python raises the TypeError. The scheduler's per-case loop catches it and skips the case, so that case gets no cost that hour. The scheduler log has 708 of these, all from this line.

The NULL comes from the project API. The column defaults only apply on insert, and project updates use `exclude_unset`, so an explicit `null` (for example, clearing the cost field in the UI) is saved as NULL. I did not confirm which project or update caused it in these logs.

**Fix:**
- `src/dispatch/project/models.py`: the defaults are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and Pydantic defaults use them, so the values live in one place.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` falls back to each default separately when its value is `None`. I checked for `None` rather than falsiness, so a legitimate 0 is not replaced.

**Tests** in `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate__falls_back_to_project_defaults` covers both fields missing, only cost missing, and only hours missing.
- `test_calculate_case_response_cost_new__project_without_cost_settings` checks the new-model path that raised in the logs.

Both fail on the original code and pass with the fix.

**Results:** `tests/case_cost` passes (22 tests). The full suite has 362 passed, 4 skipped, and the same 8 failures as before (ai, restricted case filter, entity), which fail on the untouched code too.

**Not changed:** `src/dispatch/incident_cost/service.py:133` has the same unguarded division. Incident costs for projects with NULL values will hit the same error. Say if you want me to apply the same fix there.

----- next turn -----

## Incident recap

**Cost bug (inflated case response costs):** Commit `20f33137` (fix(case_cost): use the latest status timestamp as the cost cut-off) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function sets the cut-off for billed role time from the stable, escalated and closed timestamps. The code comment says "earliest", so `min` was the intended behaviour.

With `max`, the cut-off moves to the latest milestone. Escalated cases are no longer recomputed by the hourly job, so their cost froze at escalation. When such a case was later marked stable, the job recomputed it up to the stable time, billing all the time in between at once. Stable cases are then frozen, so the inflated figure stuck. Five cases were affected, with increases of 1.5x to 3.6x: 5284, 5327, 5264, 5363 and 5406, between Sept 3 and Sept 12.

**Deploy:** Commit `20f33137` is an ancestor of `65f7df6e`, which was deployed as image `main-65f7df6e` on Sept 2 at 18:14Z. The scheduler restarted on it at 18:15:30Z, and the first inflated sync was Sept 3 at 11:20Z.

**Fix:** `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py` is back to `min`. A regression test covers the escalate-then-stable case. Already-inflated costs are not corrected; they need a targeted recalculation.

**Separate TypeError (hourly job failing for some cases since Sept 8):** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` without a null check. A NULL `annual_employee_cost` raised the error, and the job skipped those cases. The project API can save NULL, because project updates use `exclude_unset`. The fix falls back to the model defaults of 50,000 and 2,080. Tests cover it. The same unguarded division exists in `src/dispatch/incident_cost/service.py:133` and is not yet fixed.

**Open items:** the affected cases' costs need recalculation for the finance warehouse. I did not confirm which project or update set the NULL. The incident cost division should get the same fix.

Full test suite: 362 passed, 4 skipped, 8 failed. The 8 failures are in the ai, restricted case filter and entity tests, and they fail on the untouched code too.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost