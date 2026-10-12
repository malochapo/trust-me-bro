## Recap

**Cost inflation**
- **Cause:** commit `20f33137` ("use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in the participant role time calculation.
  - The cut-off for a case's cost is meant to be the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, a case marked stable and later escalated or closed kept accruing cost until the later timestamp.
- **Deploy:** it shipped in image `main-65f7df6e` on 2025-09-02 at about 18:14Z. The deploy before it, `main-3e0445ff`, predates the commit.
- **Effect:** five cases were flagged by finance's sync, with jumps of +147% to +265%.
  - They are 5284 (09-03), 5327 (09-05), 5264 (09-08), 5363 (09-09, $2,261 to $6,241) and 5406 (09-12).
  - Smaller inflations may exist that the sync didn't flag.
  - Any case that has more than one of the three timestamps has probably been overstated since the deploy.
- **Fix:** restored `min`. The regression test is `test_case_cost_stops_at_earliest_status_timestamp`. It fails on the old code and passes on the fix.
- **Not verified:** I didn't check the database rows. I haven't confirmed that the five flagged cases have the timestamp combinations I described. I also can't explain why 5284's jump landed on 09-03 11:20 and not right after the deploy.
- **Warehouse:** the fix only changes costs going forward. The warehouse values from 2025-09-02 onward are still inflated until the scheduler recalculates after the next deploy.

**Hourly TypeError (separate issue)**
- **Cause:** `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. Both are nullable project columns, and a project with either one NULL raises `TypeError`. The log has 708 of these errors.
  - Both the new and classic cost models call it, so affected cases got no cost update.
  - The logs don't say which project has NULLs or why it started on Sep 8.
- **Fix:** it now falls back to the `Project` model's column defaults for whichever value is missing. Two new tests cover it.
- **Open item:** `src/dispatch/incident_cost/service.py:133` has the same unguarded division and is unfixed.
- Both fixes are uncommitted. The 22 tests in `tests/case_cost` pass.

**FIRST_INFLATED caveat.** I used 2025-09-03, the first flagged jump in the sync log. The jumps are the only evidence I have, so an earlier unflagged inflation on 09-02 can't be ruled out.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost or business_year_hours