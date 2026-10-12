**Root cause:** commit `20f33137` (“fix(case_cost): use the latest status timestamp as the cost cut-off”, Jordan Lee, 2025-09-02) changed one line in `src/dispatch/case_cost/service.py`, `get_participant_role_time_seconds`. The cost cut-off for a case that is no longer new or triage went from `min(stable_at, escalated_at, closed_at)` to `max(...)`. That line is still `max` at HEAD (line 353).

**Why it shows up as a jump:** a case stops accruing cost at its cut-off. With `min`, the cut-off was the first milestone. With `max`, it is the latest one. When a case is escalated and later marked stable, the cut-off moves from the escalation time to the stable time. Every participant's hours between those two points are booked in one step at the moment the case is marked stable.

**Case 5363 matches this:**
- It was escalated around 2025-09-05 16:20 UTC. Its cost rose to 2261 that hour and then stayed flat for about 92 hours. The cost-sync log has no change for 5363 between 09-05 16:20 and 09-09 12:20.
- It was marked stable on 09-09. The next sync booked 2261 → 6241 (+3,980) in one step, and the sync flagged it at 12:20:04.

So the step on 09-09 is the stable transition moving the cut-off forward. The cost is not growing at the clock rate.

**The deploy that shipped it:** image tag `main-65f7df6e`, which contains `20f33137` (checked with `merge-base --is-ancestor`). The Kubernetes events show `dispatch-web` rolling to it at 2025-09-02 18:14:36 UTC and `dispatch-scheduler` at 18:15:24 UTC. Later deploys (`main-51546e13`, 09-04) kept the change, so they did not fix it.

**Ruled out:**
- **The finance sync job.** It moved from 1.4.2 to 1.5.0 on 09-01 at 10:20, but the per-hour diffs before and after look normal, and it only copies values from the Dispatch API. The jumps originate in Dispatch's calculation.
- **The other commits in the same window**, such as `65f7df6e`, `beb60cc4` and `51546e13`. None of them touch case cost.

**Things I could not confirm:**
- The 09-05 09:20 step (case 5363, 3425 → 1243) is not explained by the cut-off change alone. It needs the database to check.
- The scheduler logs about 700 failures of `get_hourly_rate` (`unsupported operand type(s) for /: 'NoneType' and 'int'`, from `project.business_year_hours` being `None`). That means some case costs are not being recalculated. It would make costs stale rather than inflated, so I don't think it causes this, but I did not check when it started.

**Suggested next step:** confirm against the database that 5363's `escalated_at` is around 09-05 16:00 and `stable_at` is around 09-09 12:00. Then decide how the affected costs should be corrected in the warehouse and whether the cut-off should revert to `min` or be defined differently. I have not changed any code.

----- next turn -----

The fix is in, and the regression test fails on the old code and passes on the new code. I have not committed anything.

**The change**
- `src/dispatch/case_cost/service.py:353`: `max(timestamps)` → `min(timestamps)`. This restores the behaviour from before `20f33137`. The comment just above it already says "earliest relevant timestamp for cost calculation cut-off", so the commit's `max` contradicted the code's own intent.
- `tests/case_cost/test_case_cost_service.py`: new test `test_case_cost_stops_at_first_milestone_when_escalated_then_stable`. The participant joins at T-5h, the case is escalated at T-3h and marked stable at T-1h. The expected time is 2h (7200 s), so cost stops at escalation. The stable-time test that already existed only set `stable_at`, which is why it did not catch the bug.

**Verification**
- Before the fix, the new test fails with `14400.0 == 7200`, which is the 4-hour-to-stable value.
- After the fix, `tests/case_cost`, `tests/case_cost_type`, `tests/incident_cost` and `tests/feedback` pass (54 passed, 1 skipped).
- Full suite: 360 passed, 8 failed, 4 skipped. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py::test_restricted_case_filter_with_test_data` and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. The same 8 fail on the untouched HEAD, so they predate this change and I did not investigate them.
- `ruff` is not installed in this environment, so I did not lint.

**Still open**
- The warehouse already holds the inflated values from 09-02 onward. I have not corrected them. The sync job upserts changed rows, so the corrected values should reach `finance.case_response_cost` on the next runs, but I have not confirmed that against the warehouse. Case 5363 should drop back to its escalation-time value once the fix is live.
- The 09-05 09:20 drop on case 5363 (3425 → 1243) is still unexplained. It is not part of this fix.
- The scheduler's `get_hourly_rate` errors (`business_year_hours` is `None`) are a separate issue. They leave some costs stale and I have not looked into them.

----- next turn -----

The hourly case cost job now gives those cases a cost. A project with no annual employee cost or no business year hours uses the project model's defaults (50,000 and 2,080). I have not committed anything.

**Cause:** `get_hourly_rate` in `src/dispatch/case_cost/service.py` divides `project.annual_employee_cost` by `project.business_year_hours` with no `None` check. The model's `Column(default=...)` values only apply when a row is inserted, so projects whose rows have NULL in either column raise `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler log has 708 of these, first on 2025-09-08 15:55 and climbing to about 150 a day. The failing case is skipped, so it gets no cost.

**Fix:**
- `src/dispatch/project/models.py`: the defaults are now module-level constants, `DEFAULT_ANNUAL_EMPLOYEE_COST = 50000` and `DEFAULT_BUSINESS_YEAR_HOURS = 2080`. The column defaults and the Pydantic schema use them too, so the fallback can't drift from the model.
- `src/dispatch/case_cost/service.py`: `get_hourly_rate` substitutes the constant for each missing value, separately, and then divides as before.

**Tests**, added to `tests/case_cost/test_case_cost_service.py`:
- `test_get_hourly_rate_uses_project_defaults_for_missing_values` covers both values missing, only the cost missing, and only the hours missing.
- `test_calculate_case_response_cost_project_without_cost_settings` checks that the new-model cost is calculated and positive for a project with both values unset. This is the path the scheduler was failing on.

Both failed before the fix with the `TypeError` and pass now.

**Verification:** the case cost, incident cost, project and case cost type suites pass (48 tests). The full suite has 362 passing, and the same 8 failures as before (AI service, one database filter test, one entity test). Those predate this change, and I did not investigate them.

**Not done:**
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division. I did not change it because you asked about the case cost job. The same fix would apply there. Its scheduler job has not logged this TypeError in these logs, but nothing stops it from hitting the same projects.
- Existing case costs for these projects were never written, so the next hourly run should create them. I have not checked that against the database.
- I didn't check whether these projects had NULLs for a reason (for example, a migration or an import), which would matter for whether the defaults are the right answer for them. That needs someone who knows the data.

----- next turn -----

Here is the recap for the incident report. Both code fixes are uncommitted in the working tree, and the warehouse rows are not corrected yet.

**Cost inflation**
- Commit `20f33137` (2025-09-02, Jordan Lee) changed the case cost cut-off from `min` to `max` over stable, escalated and closed timestamps. The code comment just above it says "earliest relevant timestamp", so the change contradicted the intent of that code. Costs accrued between escalation and stable were then booked all at once when the case was marked stable.
- It went to production in image `main-65f7df6e`, rolled out to `dispatch-web` at 2025-09-02 18:14 UTC and to `dispatch-scheduler` at 18:15 UTC.
- The first case inflated in the sync log is case 5284, flagged at 2025-09-03 11:20 (3331 → 8804). No single-hour jump above 300 appears between the deploy and that flag, so 2025-09-03 is the earliest inflated case I can see. The sync log flags only some jumps, so an earlier smaller one can't be ruled out.
- Fix: `src/dispatch/case_cost/service.py` now uses `min`. Regression test: `test_case_cost_stops_at_first_milestone_when_escalated_then_stable`. It fails before the fix (14,400 s vs 7,200 s) and passes after.

**Hourly TypeError**
- `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` without a `None` check. The log has 708 of these from 2025-09-08 on. The affected cases were skipped and got no cost.
- Fix: a `None` value now falls back to `DEFAULT_ANNUAL_EMPLOYEE_COST` (50,000) or `DEFAULT_BUSINESS_YEAR_HOURS` (2,080), defined once in `src/dispatch/project/models.py`. Two regression tests cover this, and both failed before the fix and pass now.
- The full suite has the same 8 failures as before my changes, in the AI service, one database filter test and one entity test. They are unrelated to these changes.

**Open items**
- The warehouse rows inflated since 09-02 are not corrected. The sync upserts changed values, so they should correct on the next runs, but that is not verified.
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division and was not changed.
- The scheduler's `get_hourly_rate` failures and the case 5363 drop on 09-05 are still unexplained.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost
```