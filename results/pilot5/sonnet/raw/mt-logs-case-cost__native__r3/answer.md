## Recap

**What happened.** Since early September, case response costs in the finance warehouse were several times higher than before. For example, case 5363 went from $2,261 to $6,241 on 2025-09-09. Nobody had changed rates or cost models.

**Root cause.** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in the function that finds when a participant's cost stops accruing. The timestamps are the case's `stable_at`, `escalated_at` and `closed_at`. The cut-off was supposed to be the earliest of them. With `max`, a case that has several of them keeps accruing cost up to the latest one.

**Deploy.** `main-65f7df6e` went out on 2025-09-02 at about 18:14–18:15 UTC and included `20f33137`. The previous image, `main-3e0445ff`, did not. The later deploy `main-51546e13` on 09-04 only carried the bug forward.

**Evidence.**
- There were no cost-spike warnings in `cost-sync.log` before the deploy.
- After it, five Stable cases were flagged with jumps of 147–265%.
- The first was case 5284 on 2025-09-03 at 11:20 UTC (3331 → 8804).
- Case 5356 on 09-06 also rose by about 390, roughly double its hourly norm, and was not flagged.
- Cost-sync 1.5.0, hourly rates and cost models are ruled out.

**Fix and test.** `min` is restored. The regression test `test_case_cost_stops_at_earliest_status_timestamp` fails on the buggy code and passes now.

**Second problem.** The hourly TypeError since 2025-09-08 came from a project whose `annual_employee_cost` or `business_year_hours` is NULL. `get_hourly_rate` divided `None` by an `int`, so those cases got no cost. It now falls back to the `Project` model defaults, with a test.

**Open items for the report.**
- The fixes are uncommitted and not yet deployed.
- Costs for cases that reached Stable since 2025-09-02 18:15 UTC need recalculating and re-syncing to the warehouse. The sync only flags jumps above about 100%, so smaller inflation went unflagged.
- I don't know which project has the NULL, or how it got there. A project update that saved an explicit null is my guess.
- `incident_cost/service.py` has the same unguarded division.
- The `FIRST_INFLATED` date is the first case flagged in the sync log. Smaller inflation earlier than that could exist but wasn't visible in the logs.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost