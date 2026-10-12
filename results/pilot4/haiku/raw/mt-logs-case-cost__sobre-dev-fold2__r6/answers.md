**Root cause:** commit `20f33137` (Jordan Lee, Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed one line in `get_participant_role_time_seconds`, `src/dispatch/case_cost/service.py:353`, from `min(timestamps)` to `max(timestamps)`. That moves the cost cut-off for every participant role from the first of stable/escalated/closed to the last. Nothing in the rate tables or cost models changed, which matches what finance saw.

**Why this is the bug:** the function's own comment at line 332 says "Determine the earliest relevant timestamp for cost calculation cut-off". The code after the change contradicts that. Response effort should stop when the case first became stable, escalated, or closed. With `max`, a participant assigned to a case still accrues time until the latest of those events, so a case that goes stable and then stays open or is closed days later accrues cost for all of that time.

**Shipped to production:** the events log shows the `dispatch` image changing to `main-65f7df6e` on **2025-09-02 at 18:15Z** (`dispatch-web` rollout to `zrhzjwmzrh`). That image is `65f7df6e`, which contains `20f33137` (confirmed with `git merge-base --is-ancestor`). The commit was merged at 09:29 PDT (16:29Z), before the rollout. The image before it, `main-3e0445ff`, does not contain the commit. So the Sep 2 18:15Z rollout is the first production deploy that carries the bug.

**Ruled out:**
- **cost-sync 1.5.0:** it went live Sep 1, a day before the Sep 2 rollout. It only copies numbers from Dispatch's API and doesn't compute costs.
- **Other `dispatch` image changes:** Aug 27 (`b01a1aba`→`3e0445ff`) predates the commit. Sep 4 (`→51546e13`) doesn't touch `src/dispatch/case_cost/` (verified with `git diff`).
- **Other commits in the window:** `65f7df6e` (the image's tip) changes only the case-filter UI and database filter code. Nothing else in the range touches `case_cost`.

**Caveats:**
- The logs don't include case 5363's status timestamps, so I couldn't reproduce its exact $2,261 → $6,241 figure from the code. The mechanism explains the direction and the timing: the cut-off jumps from the earlier escalation to the stable timestamp on Sep 9.
- The hourly per-case ratios are noisy. Some large jumps already appear in late August, before the Sep 2 rollout. So the logs alone don't show a clean step on Sep 2; the code history and image timeline are what pin it down.
- The commit's message says "latest status timestamp", so the author may have meant `max` on purpose. The intent is still unconfirmed, but the code comment and the cost semantics both point to `min`.

No code was changed. The fix is probably reverting `max` to `min` on `service.py:353`, plus a regression test for a case with escalated and later stable timestamps. Before deciding on that, you'd want to confirm the intended semantics with whoever wrote `20f33137`, and decide how to handle the costs already written to the finance warehouse from Sep 2 onward.

----- next turn -----

The cost cut-off now uses the earliest status timestamp again, and a regression test covers the case that broke. I did not commit.

**Fix:** `src/dispatch/case_cost/service.py:353` changes `max(timestamps)` back to `min(timestamps)`. This matches the function's comment about the earliest cut-off.

**Regression test:** `test_get_participant_role_time_seconds_uses_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`. It builds a closed case with an assignee who was assigned 4 hours earlier, with escalation at 3 hours ago, stable at 2 hours ago, and closure at 1 hour ago. The expected time is 1 hour, the span up to escalation. Against the buggy code it fails with `10800.0 == 3600`, which is the 3-hour overcharge. With the fix it passes.

**Test results** (`python -m pytest`, PostgreSQL running locally):
- `tests/case_cost` and `tests/case_cost_type`: 25 passed.
- `tests/case`: 15 passed.

I did not run the full test suite, only the case and cost areas the change touches.

**Still open:** the warehouse already holds inflated `case_response_cost` values from Sep 2 onward. This fix stops new overcharges but doesn't correct those rows. Finance will need a backfill, which is a separate decision for you and them.

----- next turn -----

The `TypeError` comes from projects whose `annual_employee_cost` or `business_year_hours` is `NULL`. Cases in those projects now get a cost using the project model's defaults, and I added tests for it.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours`. Both columns are nullable, and the model's `default=` only fills a value on insert. A project whose values are `NULL` therefore raises `unsupported operand type(s) for /: 'NoneType' and 'int'` each time the case cost job reaches one of its cases. The scheduler logs that and moves on, so the other cases still get costs. The logs show 708 of these errors. The first is on Sep 6, and the hourly runs have failed from Sep 8 onward.

I haven't confirmed which path writes the `NULL`s. The logs don't name the affected projects.

**Fix:**
- `src/dispatch/project/models.py` now defines `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and the Pydantic defaults use these constants, so the fallback and the model defaults can't drift apart.
- `get_hourly_rate` substitutes each default for a `None` value, separately for each field.

**Tests** (in `tests/case_cost/test_case_cost_service.py`):
- `test_get_hourly_rate__missing_values_use_project_defaults` is parametrized over the three missing-value combinations.
- `test_calculate_case_response_cost__project_without_cost_settings` runs the new-model cost path on a project with both values `NULL`. This is the path the scheduler hits, and it asserts a positive cost at the default rate.

I checked that the new tests fail with the reported `TypeError` on the old rate code, then pass with the fix. Tests for `tests/project`, `tests/incident_cost`, `tests/case`, `tests/case_cost`, and `tests/case_cost_type` pass (65 tests). That set includes the earlier `min` fix, which is still in place. I did not commit.

**Not changed:**
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division for incidents. The incident cost job may hit the same `TypeError` for these projects. The incident path is outside the case-cost request, so I left it alone.
- `src/dispatch/individual/service.py:104-107` already substitutes the same defaults, so you could point it at the new constants too.

----- next turn -----

The first hourly run after the rollout is at 18:20Z on Sep 2, four minutes after the image went out. The logs don't show each case's status timeline, so I can't prove that run's changes came from this bug. I'll use Sep 2 as the first inflated date and flag that.

## Recap: case cost inflation and the hourly TypeError

**Symptom.** Since early September, finance's warehouse has received case response costs several times higher than before. Dispatch's hourly scheduler job also logs a `TypeError` for a few cases each hour, starting Sep 6 and running steadily from Sep 8.

**Root cause 1: the cost cut-off used the latest status timestamp.** Commit `20f33137` (Sep 2) changed `min` to `max` when picking the participant-role cut-off from `stable_at`, `escalated_at`, and `closed_at`. The function's own comment calls for the earliest of these. With `max`, participants kept accruing cost until the last status change, so a case that was escalated and later stable or closed was charged for the gap. The image `main-65f7df6e` shipped it to production on Sep 2 at 18:15Z. The fix changes `max` back to `min`, with a regression test that fails on the old code (`10800.0 == 3600`).

**Root cause 2: unguarded hourly rate.** `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. A project whose `annual_employee_cost` is `NULL` raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler logs the error and skips the case, so those cases were missing costs. The fix substitutes the project model's defaults (`50000` and `2080`, now named constants in `project/models.py`) for missing values, with tests for each missing-value combination and for the full cost path. I have not confirmed which code path writes the `NULL`s.

**Verification.** `python -m pytest` passes on the case, case-cost, case-cost-type, project, and incident-cost test suites (65 tests). The new tests fail on the old code. Nothing is committed.

**Open items:**
- The warehouse still holds inflated `case_response_cost` rows from Sep 2 onward. The fix doesn't correct them, so finance needs a backfill.
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division, so the incident cost job may hit the same `TypeError`. I didn't change it.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-02
MISSING_SETTING: annual_employee_cost