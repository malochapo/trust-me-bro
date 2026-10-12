**Root cause:** commit `20f33137` (Jordan Lee, Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py:353`, from `min(timestamps)` to `max(timestamps)`. The function picks the cut-off from a case's `stable_at`, `escalated_at` and `closed_at`. With `max`, participant time keeps accruing until the latest of those milestones instead of stopping at the first. Hours, and therefore classic cost, inflate once a case has more than one milestone.

**The deploy:** image `registry.example.com/dispatch:main-65f7df6e` rolled out on 2025-09-02 at 18:14 UTC (`events.log`). The `dispatch-scheduler` pod was recreated on that image at 18:15 and the scheduler logged "Starting scheduler" at 18:15:30. Commit `65f7df6e` (#6206) contains `20f33137`, so that image shipped the change. Later deploys did not revert it: `main-51546e13` (Sep 4 16:52) and the Sep 10 scheduler restart both ran code that still has `max`, and `HEAD` still has it at line 353.

**Evidence and gaps:**
- The code contradicts itself. The docstring and inline comment say "Determine the **earliest** relevant timestamp for cost calculation cut-off", and the `renounced_at` logic also takes the earlier time. The commit title says "latest". I read the commit as the mistake, since it reverses the documented rule, but the author should confirm their intent.
- The case-5363 jump (`cost-sync.log:8921`, Sep 9 12:20 UTC, classic 2261 → 6241) fits this mechanism: if escalation happened before the case went stable, `max` moves the cut-off from the escalation time to the stable time. But the logs contain no per-case timestamps, so I could not check the numbers against the case's milestones.
- I could not confirm "several times" across all cases. The per-hour deltas in `cost-sync.log` are noisy and show no clean break at 18:14 UTC on Sep 2. That may be because the warehouse only reports cases whose costs changed.
- I did not run the tests. The existing stop-at-stable test (`tests/case_cost/test_case_cost_service.py:355`) covers only a single milestone, so it would not catch this.

**Next steps (no code changed):** revert line 353 to `min`, and add a test with `escalated_at` earlier than `stable_at` that asserts the cut-off is the earlier one. Then decide how to correct the finance warehouse rows written since Sep 2, which the hourly sync will not fix on its own.

----- next turn -----

I reverted the cut-off to `min`, and added a regression test that fails on the buggy code and passes on the fix.

**Fix:** `src/dispatch/case_cost/service.py:353` is back to `min(timestamps)`. Participant time stops at the earliest of `stable_at`, `escalated_at` and `closed_at`, which matches the function's docstring and comment.

**Regression test:** `test_case_cost_stops_at_first_milestone` in `tests/case_cost/test_case_cost_service.py`. The case is escalated one hour ago and marked stable ten minutes ago. Participant time should stop at the escalation. I checked that it fails with `max` (the buggy line) and passes with `min`.

**Test results** (`python -m pytest`, PostgreSQL running locally):
- `tests/case_cost/test_case_cost_service.py`: 20 passed
- `tests/case_cost` and `tests/case_cost_type`: 25 passed

The commit title (`use the latest status timestamp`) says "latest", but the function's own comment and docstring say "earliest". I went with the code's documented rule. If the author meant "latest" on purpose, that conflicts with the comment and this test would need to change.

I haven't committed anything. The warehouse rows written since the Sep 2 rollout are still wrong. The hourly sync will only correct cases whose costs change again, so those rows will need a backfill, which is a decision for you and finance.

----- next turn -----

The TypeError is fixed, and the cases that hit it now get a cost. The fix is uncommitted in the working tree.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `annual_employee_cost / business_year_hours`. When a project has either field set to `NULL`, that division raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The error aborts the whole case's cost calculation, so the classic cost is skipped as well. The logs show 708 of these between Sep 8 and Sep 14, and they don't name the project, so I couldn't identify which project has the `NULL` values.

**Fix:** When either value is `None`, `get_hourly_rate` now uses the project model's column defaults, which are 50000 and 2080. The module reads those defaults from `Project.__table__` at import time, so they stay in sync with the model.

**Tests** (`tests/case_cost/test_case_cost_service.py`):
- `test_get_hourly_rate_uses_project_defaults_when_unset` covers each field being unset, and both unset.
- `test_calculate_case_response_cost_new_when_project_values_unset` checks that the new cost model still returns a positive cost.

Both tests fail against the old code and pass with the fix. `tests/case_cost` and `tests/case_cost_type` pass: 27 tests.

**Not changed:** `src/dispatch/incident_cost/service.py:131` has the identical `get_hourly_rate`, so incident costs will hit the same TypeError for a project with `NULL` values. I left it alone because you asked about the case cost job. It is a one-line-for-line change if you want it.

----- next turn -----

## Recap

**Cost inflation (the classic cost jump).** Commit `20f33137` (Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function picks the cut-off for participant time from a case's `stable_at`, `escalated_at` and `closed_at`. With `max`, participant time runs to the latest milestone instead of the first, which inflates hours and classic cost. The function's docstring and comment say "earliest", so I treated the commit as the mistake. Its title says "latest", so the author should confirm the intent. The fix restores `min`, and a regression test fails with `max` and passes with `min`.

The bug shipped in image `main-65f7df6e`, rolled out to `dispatch-web` and `dispatch-scheduler` on 2025-09-02 at 18:14 UTC. The scheduler restarted onto it at 18:15:30. Later images (`main-51546e13`, and the Sep 10 scheduler restart) still ran the `max` code, and HEAD had it until my fix.

**Hourly TypeError.** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. When the project's `annual_employee_cost` is `NULL`, the division raises a `TypeError`, which aborts the whole case's cost calculation, classic cost included. The fix uses the project model's column defaults (50000 and 2080) for any unset value. Two new tests cover this; both fail against the old code and pass with the fix.

**Not verified:**
- The case-5363 jump on Sep 9 (2261 → 6241) fits the `max` mechanism, but the logs have no per-case milestone timestamps, so I could not confirm it.
- The logs show no clean break in total classic cost at the rollout, so I could not confirm the size of the effect across all cases.
- `FIRST_INFLATED` below is the rollout date, not a verified first inflated case.
- `incident_cost/service.py:131` has the same `get_hourly_rate` bug and is not fixed.

**Open items:** nothing is committed. The warehouse rows written since Sep 2 need a backfill, which is a decision for finance.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-02
MISSING_SETTING: annual_employee_cost
```