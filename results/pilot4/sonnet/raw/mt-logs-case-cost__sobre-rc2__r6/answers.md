**Root cause:** commit `20f33137`, "fix(case_cost): use the latest status timestamp as the cost cut-off" (Jordan Lee, 2025-09-02 09:29 PDT). It changed one line in `get_participant_role_time_seconds` in `src/dispatch/case_cost/service.py`:

```
- participant_role_renounced_at = min(timestamps)
+ participant_role_renounced_at = max(timestamps)
```

`timestamps` holds `stable_at`, `escalated_at` and `closed_at`. Cost accrual for a participant role stops at the earliest of them, which was the intent of the "cut-off" comment and the "earliest relevant timestamp" wording. With `max`, accrual runs to the latest one. Any case with more than one of those timestamps, such as one escalated and then marked stable, is now billed for the extra time between them. The classic cost model also scales up long durations through `HOURS_IN_DAY`, so the overcount can be large.

The hourly job in `case_cost/scheduled.py` stops recomputing a stable case once its cost was updated after `stable_at`. That freezes the inflated number, which is why the finance team sees a single step change at the moment of "stable". That matches `dispatch-default-security-5363`, which went from $2,261 to $6,241 in the 2025-09-09 12:20Z sync.

**The deploy that shipped it:** `registry.example.com/dispatch:main-65f7df6e`, rolled out on 2025-09-02.
- The db-upgrade job started at 18:14:09Z.
- The scheduler was replaced at 18:14:41Z–18:15:24Z.
- `65f7df6e` is the commit that sits after `20f33137` in main, so it is the first build that contains the change. The build before it was `main-3e0445ff` (2025-08-27), which doesn't contain it.
- The later deploy `main-51546e13` (2025-09-04 16:52Z) also contains it, but it is not the first.
- The scheduler pod restart on 2025-09-10 at 03:12Z ran the same `51546e13` image, so it is not a new deploy.

**Other explanations I ruled out:**
- case-cost-sync went from 1.4.2 to 1.5.0 on 2025-09-01 at 10:20Z. After that there were no flagged rows until 2025-09-03, so the sync job isn't the cause.
- The first flagged jump, case 5284 (+164%), is at 2025-09-03 11:20Z, after the deploy. The six flags are on 09-03, 09-05, 09-08, 09-09 and 09-12 (two on 09-03), all on stable cases. Each flagged case is one that became stable after the deploy.

**What I couldn't verify:** the logs don't contain `escalated_at` or `stable_at` values, so I haven't confirmed that case 5363 had both timestamps set. The mechanism fits the data, and a database check on those cases would confirm it.

**Impact and fix:** cases that went stable or closed since 2025-09-02 18:15Z have inflated stored costs, and these won't correct themselves. Fixing it means reverting the `max` back to `min`, deploying, and recalculating the affected cases' costs before finance re-syncs. I haven't changed any code, as you asked.

----- next turn -----

I've reverted the cost cut-off to `min(timestamps)` in `src/dispatch/case_cost/service.py`, and added a regression test. The `tests/case_cost` suite passes (20 tests). I haven't committed anything.

The new test, `test_case_cost_stops_at_earliest_status_timestamp` in `tests/case_cost/test_case_cost_service.py`, covers three cases with a role that is still active:
- **Escalated, then stable:** cost stops at `escalated_at`.
- **Also closed:** cost still stops at `escalated_at`.
- **No escalation:** cost stops at `stable_at`, not `closed_at`.

With the fix stashed, the test fails against the old `max` code, so it would have caught the bug. The existing test only set `stable_at`, which is why it missed this.

The deploy alone won't correct costs already stored. After shipping, someone still has to recalculate the cases that went stable or closed since 2025-09-02 18:15Z. The hourly job skips stable cases whose cost was updated after `stable_at`, so those will keep their inflated numbers until recalculated. Finance should re-sync afterward.

----- next turn -----

The TypeError comes from `get_hourly_rate` dividing a `NULL` project value, and it's fixed. The case cost tests and the project tests pass (28).

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `annual_employee_cost / business_year_hours`. Both are nullable columns on `Project`, and the project API schema accepts `None` for them. The `default=` on the columns only applies when a row is inserted without a value, not when a value is set to `NULL`. For a project with a `NULL` in either field, the division raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`.

**Where it shows in the logs:** The first one is at 2025-09-08 15:55 in `scheduler.log`, and there are 708 of them in total. They come from `calculate_case_response_cost_new` (line 466), and the hourly job catches each one and skips that case, so those cases never get a cost. No deploy happened after 2025-09-04, so I believe the project values were cleared around 2025-09-08. The logs don't show who or what did it, so that is a guess. I haven't confirmed which projects are affected.

**Changes:**
- `src/dispatch/project/models.py` now has `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`, and the column defaults use them.
- `get_hourly_rate` falls back to those constants when the annual cost is `None`, or when the hours are `None` or 0. Treating 0 hours as missing is my addition, since it would otherwise raise a division error. Each value falls back independently.
- Two new tests in `tests/case_cost/test_case_cost_service.py`: one for the hourly rate with either or both values missing, and one that computes a full case cost for a project with both unset. Both fail without the fix.

**Not changed:** `incident_cost/service.py` has an identical `get_hourly_rate` with the same bug. I left it alone because you asked about case costs. It's a quick change if you want it.

**Data:** The projects still have `NULL` in the database. The code now handles that, but you may want to set real values or stop the API accepting `None`.

Nothing is committed.

----- next turn -----

**Recap**

- **Cost inflation:** `20f33137` changed `min(timestamps)` to `max(timestamps)` in the cost cut-off. Cost then ran to the latest of `stable_at`, `escalated_at` and `closed_at`. It reached production in `main-65f7df6e`, deployed 2025-09-02 at 18:14Z (the scheduler was replaced by 18:15Z). The first inflated cost I can see is case 5284 on 2025-09-03: classic 3331 → 8804 (+164%) at 11:20Z, flagged by finance's job. Other large jumps between the deploy and that sync were small new cases accruing normally. Smaller inflations may exist that the sync's flagging threshold missed, so that date is the first one visible in the logs.
- **Fix:** the cut-off is back to `min`, with a regression test. Costs already stored for cases that went stable or closed since 2025-09-02 18:15Z still need recalculating, and finance should re-sync afterward.
- **TypeError:** it started 2025-09-08 (708 occurrences) in `get_hourly_rate`. Every one reads `unsupported operand type(s) for /: 'NoneType' and 'int'`. The `None` is on the left of the division, so it is `annual_employee_cost`. `business_year_hours` was an int in all of them. The fix falls back to the model defaults (50000 and 2080) when either is missing, with tests. I don't know what cleared the setting, or which projects are affected.
- **Open items:** the identical `get_hourly_rate` in `incident_cost/service.py` is unfixed. Nothing is committed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost