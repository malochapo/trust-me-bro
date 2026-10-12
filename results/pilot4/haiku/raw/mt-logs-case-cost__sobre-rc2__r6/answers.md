The root cause is commit `20f33137`, which changed the case cost cut-off from the earliest status timestamp to the latest. It reached production in image `main-65f7df6e` on Sep 2. I haven't changed any code, and I couldn't run the cost calculation against real data, so the per-case mechanism below is inferred from the code and the log timing.

**The change**

In `src/dispatch/case_cost/service.py` (around line 353), `get_participant_role_time_seconds` picks the cut-off from the case's `stable_at`, `escalated_at` and `closed_at`:

```python
participant_role_renounced_at = max(timestamps)   # was min(timestamps)
```

- The function's own comment still says "Determine the earliest relevant timestamp for cost calculation cut-off" (line 332), so the code now contradicts its comment.
- Before the change, a case stopped accruing participant time at its earliest status change.
- After the change, it stops at its latest one. When a case is marked Stable after being escalated, the participant time between escalation and stabilisation is now billed. Nothing else in the cost path changed.
- The existing test (`tests/case_cost/test_case_cost_service.py:355`) only sets `stable_at`, so `min` and `max` give the same result. The test cannot detect this regression.

**Deploy that shipped it**

- `20f33137` (Jordan Lee, Sep 2 09:29 PT) is an ancestor of `65f7df6e`.
- `events.log` shows `dispatch-web` and `dispatch-scheduler` pulling `registry.example.com/dispatch:main-65f7df6e` at **2025-09-02 18:14–18:15 UTC**.
- The later `main-51546e13` rollout (Sep 4, 16:52 UTC) doesn't explain the earlier jumps.

**Evidence the logs support**

- `cost-sync.log` flags a jump on the moment each case goes Stable, with no other change in the data:
  - case 5284, Sep 3: 3331 → 8804
  - case 5327, Sep 5: 2244 → 5539
  - case 5264, Sep 8: 3285 → 11987
  - case 5363, Sep 9: 2261 → 6241
  - case 5406, Sep 12: 1975 → 4945
- The first flagged jump, Sep 3, is the first one after the Sep 2 deploy.
- Before a case goes Stable, its cost grows smoothly, as expected for an active case. The step only happens at the Stable transition, which is what the `max` change would produce.

**Separate issue (not the inflation)**

`scheduler.log` has 1,416 `unsupported operand type(s) for /: 'NoneType' and 'int'` errors from Sep 8 15:55 onward. They come from `get_hourly_rate`, which divides `project.annual_employee_cost` by `business_year_hours`, so projects without an employee cost fail. This blocks the new cost model for those cases; it doesn't explain the classic-model inflation.

**Suggested fix (not applied)**

Revert to `min(timestamps)` to match the code comment and the pre-Sep 2 behaviour, and add a test where `escalated_at` is earlier than `stable_at`, so the two orderings give different results. Separately, decide whether the NoneType rate error should be guarded or fixed at the data level.

----- next turn -----

The cost fix is in, with a regression test. I haven't committed anything.

**The fix**

- `src/dispatch/case_cost/service.py:353` is back to `min(timestamps)`, which matches the code comment and the behaviour before commit `20f33137`.
- I didn't change the rest of the function.

**The regression test**

`test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py` covers the gap the old test missed. The participant is assigned 3 hours ago, the case is escalated 2 hours ago and marked stable 1 hour ago. Participant time should stop at the escalation, so the expected value is 1 hour of time, not 2.

- With `max` restored, the test fails.
- With `min`, it passes.

**Test results**

- `python -m pytest tests/case_cost/`: 20 passed.
- Full `python -m pytest`: 360 passed, 4 skipped, 8 failed. All 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py` and `tests/entity/test_entity_service.py`. I stashed my changes and ran those files on the original tree, and the same 8 failed, so they predate this work and aren't caused by it.

----- next turn -----

The hourly job no longer fails for projects with missing cost settings. Those projects now use the project model defaults, so their cases get a cost again. I haven't committed anything.

**Cause**

`get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours` with no null check. A project with either value NULL raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`.

- The scheduler catches the exception per case and moves on. Each affected case therefore got no cost at all, classic included, because the failure happens before the costs are saved.
- The model's column defaults (50000 and 2080) only apply when a row is inserted. Rows that already have NULL keep it.
- The logs don't name the projects, so I can't tell from them which projects are affected or why they became NULL on Sep 8. The project rows in the database would answer that.

**Fix**

- `src/dispatch/project/models.py`: the defaults are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and `ProjectBase` use them, so the values have one source. The values are unchanged.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` substitutes each missing value independently. It checks for `None` rather than falsiness, so a real `0` is still used as given.

**Tests**

Added to `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate_falls_back_to_project_defaults` covers both values missing, only one missing, and the other value set.
- `test_calculate_case_response_cost_new_with_missing_project_values` checks that the new model returns the expected amount for a project with both values NULL.

Both fail without the fix and pass with it. `python -m pytest tests/case_cost/` gives 22 passed. The full `python -m pytest` run gives 362 passed and 4 skipped. The same 8 failures as before remain, in the AI, database and entity tests, and they also fail on the original code.

**Not changed**

- `src/dispatch/incident_cost/service.py:133` has the same unguarded division. Incident costs could fail the same way for the same projects, so you may want the same fix there.
- A project with `business_year_hours = 0` still raises `ZeroDivisionError`. I didn't guard that because the request only covered NULL.

----- next turn -----

Here is the recap for the incident report. The first inflated case is the earliest large jump in the logs after the Sep 2 deploy. The earlier 5284 cost jump on Sep 3 is the only one of that size between Sep 2 and Sep 4.

**Summary**

- **What happened:** Since early September, classic case response costs for cases that went Stable were inflated, for example case 5363 went from $2,261 to $6,241 when it was marked stable on Sep 9. The cause was commit `20f33137`, which changed the cost cut-off from the earliest status timestamp to the latest. A case that was escalated and then marked stable kept accruing participant time until the stable time, so its cost was overstated. Five cases were flagged by the sync check (5284, 5327, 5264, 5363, 5406); each jump happened at the Stable transition.
- **Why it shipped:** The commit's message described the new behaviour, but the function's comment still said "earliest", and the existing test only sets `stable_at`, so it could not detect the change. The image `main-65f7df6e` rolled out to the web and scheduler pods on Sep 2 at 18:14 UTC.
- **Fix:** `get_participant_role_time_seconds` uses `min(timestamps)` again. A new test, `test_case_cost_stops_at_earliest_status_timestamp`, covers an escalation followed by a stable transition and fails on the buggy code.
- **Secondary issue:** The hourly case cost job logged a TypeError for affected cases from Sep 8 onward. Projects with NULL `annual_employee_cost` or `business_year_hours` made `get_hourly_rate` fail, so those cases got no cost at all. `get_hourly_rate` now falls back to the project model defaults (50000 and 2080), and two new tests cover it. The logs don't name the affected projects, and I haven't established why those rows became NULL on Sep 8.
- **Not changed:** `incident_cost/service.py:133` has the same unguarded division, and a project with `business_year_hours = 0` still raises `ZeroDivisionError`.
- **Tests:** The full suite has 362 passing and 8 failing. The same 8 AI, database and entity tests fail on the original code too.

**Incident report fields**

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost