**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, Sep 2) changed the cost cut-off from the earliest status timestamp to the latest. The deploy that shipped it to production is the dispatch image `main-65f7df6e`, rolled out on **Sep 2 at 18:14–18:15 UTC**.

I did not change any code.

**The change**

In `src/dispatch/case_cost/service.py`, `get_participant_role_time_seconds` decides when a case stops accruing participant time. It collects `stable_at`, `escalated_at` and `closed_at`, then picks one:

- Line 332 still says `# Determine the earliest relevant timestamp for cost calculation cut-off`.
- Line 353 was changed from `min(timestamps)` to `max(timestamps)`.

So the comment describes the old behaviour, and the code now does the opposite. Any case that was escalated and later marked Stable gets charged for the whole escalated period. That window belongs to the incident that the escalation created, so it's effectively double-counted.

**Evidence**

- Case 5363 accrued about +145 per hour from Sep 4 to Sep 5 15:20 (cost 1970 → 2116). It then sat still until Sep 9 12:20, which points to a non-new/non-triage status, most likely escalated. Its cost then jumped 2261 → 6241 exactly when it was marked Stable. A freeze followed by a jump on the Stable transition is the signature of the `max` cut-off.
- The first `WARNING ... flagged for review` on a Stable case is on Sep 3 11:20 (case 5284). Every flagged case comes after the deploy: 5284 (Sep 3), 5327 (Sep 5), 5264 (Sep 8), 5363 (Sep 9), 5406 (Sep 12).
- Deploy ancestry: `git merge-base --is-ancestor` confirms `20f33137` is in `65f7df6e` and `51546e13`, but not in `3e0445ff` (deployed Aug 27) or `b01a1aba`.
- The existing test `test_case_cost_stops_at_stable_time` (tests/case_cost/test_case_cost_service.py:355) covers only Stable with no escalation, so the change went through without a failing test.

**Caveats**

- The logs have no case timestamps, so "5363 was escalated on Sep 5" is inferred from the freeze, not read from data. The `escalated_at` value for 5363 would confirm it.
- I did not reproduce the exact 2261 → 6241 figure. Roughly 3–4 days of escalated time, under the 8-hours-per-day cap in the cost code, is the right order of magnitude.
- The cost-sync 1.5.0 rollout on Sep 1 predates the first jump, and I found no sign it caused the change.

**Separate problem, not the cause of the inflation**

The scheduler logged 708 `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'` from `get_hourly_rate` (service.py:118), because `project.annual_employee_cost` or `business_year_hours` is None for at least one project. Those cases fail in `calculate_cases_response_cost` and their costs are not saved. That leaves costs stale; it does not inflate them. It should be fixed on its own.

**Suggested next step (not done):** revert line 353 to `min`, and correct the comment or check the intent with Jordan Lee. Then add a test for escalated-then-stable, and recalculate the affected cases, which are Stable cases with an `escalated_at` before their `stable_at` since Sep 2. Confirm the affected set and the `escalated_at` values with a database query first.

The scratch script I used to bucket the cost diffs is in `/tmp/sobre-bench-work/run-066440a7825e/scratch/jumps.py`, outside the repo.

----- next turn -----

The fix is in, and the regression test fails on the buggy code and passes on the fix. Nothing is committed.

**The fix:** `src/dispatch/case_cost/service.py:353` goes back to `min(timestamps)`. A case now stops accruing participant time at its earliest end event (escalated or stable), which is what the existing comment on line 332 describes.

**The regression test:** `test_case_cost_stops_at_first_status_change_after_escalation` in `tests/case_cost/test_case_cost_service.py`. It sets up a participant assigned 3 hours ago, a case escalated 2 hours ago, and marked Stable 1 hour ago. The expected time is the 1 hour between assignment and escalation.
- With `max` in place, it fails: `assert 7200.0 == (3600 * 1)`.
- With `min` restored, it passes.

**Tests:** `python -m pytest tests/case tests/case_cost -q` gives 35 passed.

The `TypeError` from `get_hourly_rate` (708 failures in the scheduler log) is still there. It is separate from this bug, and I did not touch it.

----- next turn -----

The hourly TypeError comes from `get_hourly_rate` dividing by a NULL project value. Case cost now falls back to the project model's defaults, and the tests pass. Nothing is committed.

**Cause:** `case_cost/service.py` did `project.annual_employee_cost / project.business_year_hours` with no check. A project with either column NULL raised `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`, and the whole case's update was skipped. The model's `default=` only applies on insert. `project/service.py:update` uses `exclude_unset=True` and `setattr`, so a project update that sends an explicit `null` writes NULL. The logs don't name the project, so I haven't confirmed which project has the NULLs. I also didn't pin the timestamp of the first error; the 708 errors match the Sep 8 start you reported.

**Fix:**
- `src/dispatch/project/models.py`: the defaults are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and the Pydantic defaults use them, so the values are defined in one place.
- `src/dispatch/case_cost/service.py:get_hourly_rate`: a None value for either field falls back to the matching constant.

**Test:** `test_get_hourly_rate_falls_back_to_project_defaults` in `tests/case_cost/test_case_cost_service.py`, parametrised over the set and NULL combinations. The NULL cases raise the TypeError on the old code. I reasoned about this rather than running the old code against the test.

**Verification:** `python -m pytest tests/case tests/case_cost tests/project -q` gives 45 passed. `ruff check` and `ruff format --check` pass on the three changed files.

**Not changed, for you to decide:**
- `incident_cost/service.py:133` has the same unguarded division, so incident costs can hit the same error. I left it alone because you asked about the case cost job.
- A business year hours value of 0 still raises `ZeroDivisionError`. I only handled None, as you specified.
- Project updates can still write NULL into these columns. Blocking that, for example by rejecting nulls in `ProjectUpdate`, is a separate change.

----- next turn -----

Recap of the incident:

- **Cost inflation:** commit `20f33137` (Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed the participant-time cut-off from the earliest end event to the latest. A case escalated and later marked Stable was charged for the whole escalated period again. That window belongs to the incident. The change shipped in dispatch image `main-65f7df6e`, rolled out Sep 2 at 18:14–18:15 UTC. The first flagged inflated case was 5284 on Sep 3. I did not check the logs for earlier unflagged inflation, so Sep 3 is the first flagged date, not a proven first date.
- **Fix:** the cut-off is back to `min` (`src/dispatch/case_cost/service.py`), with a regression test that fails on the buggy code.
- **Hourly TypeError:** `get_hourly_rate` divided by project values that were NULL. The error reads `'NoneType' / 'int'`, so the NULL is `annual_employee_cost`. The project update path can write explicit nulls. Cost now falls back to the model defaults, with a test.
- **Not yet done:** both fixes are uncommitted. `incident_cost/service.py` has the same unguarded division. Project updates can still store NULL.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost