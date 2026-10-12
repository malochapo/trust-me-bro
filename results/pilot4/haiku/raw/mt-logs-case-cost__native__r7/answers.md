**Root cause:** commit `20f33137` ("fix(case_cost): use the latest status timestamp as the cost cut-off", Jordan Lee, Sept 2) changed one line in `src/dispatch/case_cost/service.py:353`, inside `get_participant_role_time_seconds`:

```python
participant_role_renounced_at = max(timestamps)   # was min(timestamps)
```

`timestamps` holds whichever of `stable_at`, `escalated_at` and `closed_at` are set. The cut-off used to be the earliest of them and is now the latest. The function's own comment still says "earliest relevant timestamp", so the code and comment now disagree.

**Deploy:** the image `registry.example.com/dispatch:main-65f7df6e` rolled out on Sept 2 at 18:14 (`events.log`), and the scheduler restarted at 18:15 (`scheduler.log`). Commit `65f7df6e` is a descendant of `20f33137` in `main`'s history, so that image contains the change. The next image, `main-51546e13`, went out Sept 4 at 16:52 and is unrelated to cost. The events log names only the image tag, so the link from tag to commit comes from git history.

**Why case 5363 jumped on Sept 9:** I could not query the database, so the timestamps below are inferred from the logs.

- Through Sept 5 the case accrued about 145 an hour, which fits an open case with no milestone.
- It then froze at 2261 from about Sept 5 16:20. That fits it being escalated, with `escalated_at` as the cut-off.
- On Sept 9 it was marked stable. With `max`, the cut-off moved to `stable_at`, so the roughly four days between escalation and stable were billed at once: 2261 → 6241.

**Other flagged cases** follow the same pattern, all Stable and all after the deploy: 5284 (Sept 3), 5327 (Sept 5), 5264 (Sept 8, 3285 → 11987), 5406 (Sept 12). The first, 5284, appeared about 17 hours after the deploy.

**Why tests missed it:** the existing `get_participant_role_time_seconds` tests in `tests/case_cost/test_case_cost_service.py` set only one milestone at a time. Running them against the current code, 3 pass, so no test combines escalated and stable.

**Things to confirm before fixing:**
- Reverting to `min` restores the pre-Sept 2 behaviour and matches the code comment. Whether `min` is the right business rule is for the cost owners to decide. The commit title says "latest", so the author had a reason I can't see. Jordan Lee is the person to ask.
- Two anomalies I could not explain from the logs: case 5363 dropped from 3425 to 1243 on Sept 5 at 09:20, and case 5274 rose from 270 to 490 on Aug 27, before the deploy.

I made no code changes.

----- next turn -----

The cut-off is back to `min`, and a regression test now covers the escalated-then-stable case. I did not commit anything.

**The fix:** in `src/dispatch/case_cost/service.py:353`, `max(timestamps)` is back to `min(timestamps)`. The cut-off is again the earliest of `stable_at`, `escalated_at` and `closed_at`, matching the function's comment and the behaviour before Sept 2. This is the only change to the service.

**The regression test:** `test_case_cost_stops_at_first_milestone_when_escalated_before_stable` in `tests/case_cost/test_case_cost_service.py`. The case is escalated 1.5 hours ago and marked stable 1 hour ago, with the participant assigned 2 hours ago. The test expects 30 minutes of cost, which is the time up to escalation. The existing tests only set one milestone at a time, which is why they missed this.

**Verification:**
- `python -m pytest tests/case_cost` passes, 20 of 20, against PostgreSQL.
- With `max` put back temporarily, the new test fails, so it does catch the bug. I then restored `min` and confirmed the suite passes again.

**Open point:** the commit title said "latest status timestamp", so the author may have had a reason for `max`. I restored `min` because the function's own comment and the pre-Sept 2 behaviour both say "earliest". Confirm the rule with the cost owners, and with Jordan Lee if needed. If `min` is right, the flagged cases should be re-run after the fix ships. Their stored costs were recalculated with the wrong cut-off, so they may need correcting in the warehouse. I have not checked that.

----- next turn -----

The scheduler's case cost job no longer raises on projects with a missing annual employee cost or business year hours. Those projects now fall back to the project model's defaults, and there is a test for it. Nothing is committed.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` computes `annual_employee_cost / business_year_hours` with no null check. The `project` columns are nullable, so a project with either value NULL raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The first one in `scheduler.log` is at 2025-09-08 15:55, and there are 708 in total. The traceback shows `calculate_case_response_cost_new` → `get_hourly_rate`. The logs do not say which projects had NULLs, and I did not check the database for why those rows are NULL. The model defaults only apply on insert, so existing rows keep NULL.

**Fix:**
- `src/dispatch/project/models.py`: the defaults are now named constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The Column defaults and the Pydantic defaults use them, so the numbers are defined once.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` falls back to those constants for either value that is missing. The function now imports them from the project model.

**Tests** in `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate_uses_project_defaults` (parametrized over four combinations of missing and set values).
- `test_calculate_case_response_cost_classic_without_project_cost_settings`, which is the end-to-end path that raised, with both values NULL.

With the fallback removed, four of the new tests fail. With it restored, `tests/project`, `tests/incident_cost`, `tests/case_cost` and `tests/case` pass, 61 in total.

**Not changed:** `src/dispatch/incident_cost/service.py:133` has the same unguarded division. Incident costs for projects with NULL values will raise the same way. I left it alone because you asked about the case cost job. It is a one-line fix if you want it in the same change.

----- next turn -----

Here is the recap for the incident report. Nothing is committed.

**What happened:** Since Sept 2, classic case response costs for some Stable cases have been inflated several times over. The cause was commit `20f33137`, which changed the cost cut-off in `get_participant_role_time_seconds` from the earliest status milestone to the latest. A case that was escalated and then marked stable kept accruing cost up to the stable time, when it should have stopped at escalation. The deploy that shipped it was `main-65f7df6e`, rolled out Sept 2 at 18:14. Example: case 5363 was frozen at 2261 from Sept 5, then jumped to 6241 on Sept 9 when it was marked stable. Other flagged cases were 5284, 5327, 5264 and 5406.

**Fix:** the cut-off is back to `min`. A regression test, `test_case_cost_stops_at_first_milestone_when_escalated_before_stable`, covers the escalated-then-stable case and fails under `max`.

**Second bug:** since Sept 8 the hourly job has logged 708 `TypeError`s. `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` with no null check, and the project columns are nullable. Missing values now fall back to the project model defaults, 50000 and 2080. The constants live in `project/models.py`. Two tests cover this, and both fail without the fallback. The `case_cost`, `case`, `project` and `incident_cost` tests pass.

**Caveats for the report:**
- FIRST_INFLATED is the first inflated cost I can identify in the logs, which is case 5284 on Sept 3. Sync diffs from the deploy onward show only normal hourly accrual, so an earlier, smaller inflation cannot be ruled out from the logs.
- Some cases show unexplained drops in the logs, such as 5317 (3098 → 1661) on Sept 2 and 5363 (3425 → 1243) on Sept 5. I did not attribute these to either bug.
- The unexplained 5274 rise on Aug 27 predates the deploy.
- `incident_cost/service.py:133` has the same unguarded division as the `TypeError`. It is not fixed.
- I did not check the database for why those project rows are NULL.
- The `case_cost` fixes have not been committed or deployed.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost