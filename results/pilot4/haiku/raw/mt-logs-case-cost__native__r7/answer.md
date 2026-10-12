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