**Root cause:** commit `20f33137` (Jordan Lee, Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed one line in `src/dispatch/case_cost/service.py:353`, from `min(timestamps)` to `max(timestamps)`. That turns the cost cut-off for non-new, non-triage cases from the earliest of `stable_at`, `escalated_at`, and `closed_at` into the latest. Any case that escalated before it went Stable (or closed later) now accrues participant time through the whole gap. Participant roles aren't renounced at stabilization, so cost keeps accruing until the later status change.

**Deploy that shipped it:** image `registry.example.com/dispatch:main-65f7df6e`. The commit is an ancestor of `65f7df6e` but not of `3e0445ff`, the previous image. `dispatch-web` rolled to `main-65f7df6e` on **2025-09-02 18:14 UTC** (11:14 PT), and the scheduler followed at 18:15 UTC. `main-51546e13` (Sep 4, 16:52 UTC) also carries the bug, but the first deploy that did was `65f7df6e`.

**Evidence the timing matches:**
- The sync's own checks flag Stable cases whose classic cost jumps at the moment they go Stable: 5284 (Sep 3 11:20 UTC, 3331→8804), 5327 (Sep 5, 2244→5539), 5264 (Sep 8, 3285→11987), 5363 (Sep 9, 2261→6241), 5406 (Sep 12, 1975→4945). The first one comes the day after the deploy.
- The cost-sync job is pinned to `case-cost-sync:1.4.2` the whole window, so the change is on the Dispatch side.
- The `min`→`max` line was last touched by this commit (blame). The earlier code and the function's own comment both say "earliest relevant timestamp for cost calculation cut-off", which matches the `min`.
- The existing test `test_case_cost_stops_at_stable_time` only sets `stable_at`, so it can't tell `min` from `max`. It doesn't cover escalated-then-stable, so CI didn't catch it.

**Caveats:**
- I couldn't query the database, so I haven't confirmed that `escalated_at` precedes `stable_at` for 5363. That is the mechanism I'm inferring, and checking those timestamps for 5363 would confirm it.
- The hourly per-case deltas are noisy across the whole window (drops and rises appear from Aug 25), so the only clean signal is the flagged Stable transitions.
- I'm not sure what the commit's author meant by "latest status timestamp". Its title contradicts the code comment, so Jordan Lee should confirm which behavior was intended before anyone reverts it.

No code was changed. The likely fix is to restore `min(timestamps)` and add a test with `escalated_at` before `stable_at`. Finance would also need the case_response_cost rows since Sep 2 recomputed or backfilled.

----- next turn -----

The cost cut-off is fixed and a regression test covers it. The full suite passes except 8 tests that already fail on the unmodified tree.

**The fix:** `src/dispatch/case_cost/service.py:353` goes back to `min(timestamps)`, so the cut-off is the earliest of `escalated_at`, `stable_at`, and `closed_at`, as the function's comment says.

**The regression test:** `test_case_cost_stops_at_earliest_stable_or_escalated_time` in `tests/case_cost/test_case_cost_service.py`. It sets `escalated_at` two hours ago and `stable_at` one hour ago, then checks that participant time stops at the escalation (3600s from a three-hour assignment). With the `max` line restored, it fails with `7200.0 == 3600`. With the fix, it passes.

**Test results:**
- `tests/case_cost/test_case_cost_service.py`: 20 passed.
- Full `python -m pytest tests`: 360 passed, 4 skipped, 8 failed. The failures are in `tests/ai/test_ai_service.py` (6 tests), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. I ran those files on a stash of my changes and the same 8 failed, so they predate this fix and aren't caused by it. I didn't investigate them.

**Things to know:**
- I didn't commit anything. The diff is two files, 33 insertions and 1 deletion.
- The `min` restore goes against the commit title "use the latest status timestamp". I went with the code comment and the cost semantics, not the title. Jordan Lee should confirm that nothing in the commit's intent needs the later timestamp.
- The existing test only sets `stable_at`, so it can't distinguish `min` from `max`. The new test covers the escalated-then-stable case, which is what the bug broke.
- Finance's `case_response_cost` rows for affected cases (Stable cases escalated before they went Stable, since Sep 2) still hold the inflated values. Those need recomputing once this is deployed. I haven't touched the warehouse.

----- next turn -----

The scheduler's `TypeError` comes from a project with `annual_employee_cost` or `business_year_hours` set to NULL. `get_hourly_rate` divides the two values without a null check, so those cases fail with no cost. Both values now fall back to the project model defaults, and the regression tests pass.

**Cause:** the 708 `TypeError`s in `scheduler.log` (Sep 8 onward) all come from `case_cost/service.py` `get_hourly_rate`: `math.ceil(project.annual_employee_cost / project.business_year_hours)` with a `None` operand. The traceback shows it is only the case-cost job. The project columns are nullable, and the model's `default=` applies only when a row is inserted through the ORM. A project row with these fields NULL keeps them NULL.

**Fix:**
- `src/dispatch/project/models.py`: two named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and the pydantic schema now use them, so the fallback and the model share one source.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` uses each default when its value is `None`. A value of `0` is still passed through, which I left alone because the request was about unset values.

**Tests** in `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate_uses_project_defaults_when_unset` checks the rate for each combination of set and unset values.
- `test_case_cost_with_unset_project_cost_fields` checks that a case on such a project still gets a positive classic cost.

Both were added to the test file. The first checks the rate arithmetic directly. The second is the path the scheduler was failing on. The `None` cases in the first test would hit the same `TypeError` on the old code.

**Results:** `tests/case_cost/test_case_cost_service.py` passes (22 tests). The full suite gives 362 passed, 4 skipped, and the same 8 failures as before (AI service, one database test, one entity test). They fail on the unmodified tree too, as I reported earlier.

**Things to know:**
- `incident_cost/service.py` has the same `get_hourly_rate` with no null check. The scheduler log has no errors from the incident job, so I didn't change it. It will fail the same way for any incident project with these fields NULL. I can apply the same fallback there if you want.
- Nothing in the repo sets these columns to NULL, so the source is probably a data change or an insert outside the ORM. The log doesn't show which projects are affected, so checking the `project` table for NULLs would confirm it.
- `tests/case_cost/test_case_cost_service.py` changed on disk while I was working. I appended the new tests to its current content and left the earlier changes in place. The earlier `min` fix and the escalated-cutoff test are still there.
- I didn't commit anything.

----- next turn -----

Recap for the incident report. Two things were fixed in `src/dispatch/case_cost/service.py`, and both are uncommitted in the working tree.

**1. Inflated case costs (the main bug)**
- Commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, Sep 2) changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. The cost cut-off became the latest of `escalated_at`, `stable_at`, and `closed_at` instead of the earliest. Cases that escalated before going Stable kept accruing participant time until the Stable transition.
- The fix restores `min`. Regression test: `test_case_cost_stops_at_earliest_stable_or_escalated_time`. It fails on the buggy line (7200s vs 3600s) and passes with the fix.
- It shipped in `main-65f7df6e`, which rolled out to `dispatch-web` on Sep 2 at 18:14 UTC (11:14 PT). The scheduler followed at 18:15 UTC. `main-51546e13` (Sep 4) also contains it.
- Earliest flagged inflated cost is case 5284 on Sep 3 at 11:20 UTC (3331 → 8804). I found no earlier Stable-transition jump after the deploy. The small increases on Sep 2–3 are new cases ramping up, not this bug.

**2. Hourly TypeError (separate)**
- The scheduler's 708 `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` errors come from `get_hourly_rate` in the same file, which divided `annual_employee_cost` by `business_year_hours` with no null check. Those projects had `annual_employee_cost` NULL (the numerator is the `None`).
- Fix: `get_hourly_rate` now falls back to `DEFAULT_ANNUAL_EMPLOYEE_COST` (50000) and `DEFAULT_BUSINESS_YEAR_HOURS` (2080). These constants now live in `src/dispatch/project/models.py` and back the model's column defaults and schema defaults. Regression tests: `test_get_hourly_rate_uses_project_defaults_when_unset` and `test_case_cost_with_unset_project_cost_fields`.
- I did not find which projects have these fields NULL, or how they got that way. The logs don't say, so the project table should be checked.

**Test status:** `tests/case_cost/test_case_cost_service.py` passes (22). The full suite has 362 passed, 4 skipped, and 8 failures in the AI service, one database test, and one entity test. Those 8 also fail on the unmodified tree.

**Open items:**
- `incident_cost/service.py` has the same `get_hourly_rate` with no null fallback. The scheduler log shows no errors from it, but it would fail the same way. I didn't change it.
- Finance's `case_response_cost` rows for affected cases still hold inflated values. They need recomputing after deploy.
- I haven't committed anything.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost