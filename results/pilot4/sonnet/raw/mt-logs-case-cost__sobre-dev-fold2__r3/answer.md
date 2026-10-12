## Recap

**Inflated costs.** Since the `main-65f7df6e` deploy on 2025-09-02 (about 18:14–18:15Z), case costs have been calculated up to the wrong end time. Commit `20f33137` changed the cut-off for a participant's time in `get_participant_role_time_seconds` from `min(timestamps)` to `max(timestamps)`. The timestamps are `stable_at`, `escalated_at` and `closed_at`. With more than one set, the later one was used, so the billed time went up. The rates and cost models were never touched.

**Evidence.**
- Before the deploy, no case's hourly change in `cost-sync.log` exceeded $221.
- After it, five jumps of $2,970–$8,702 appear: cases 5284, 5327, 5264, 5363 and 5406. Case 5363 went from $2,261 to $6,241 on 09-09.
- The first of them, case 5284 at 2025-09-03 11:20Z (+$5,473), gives the FIRST_INFLATED date.
- I scanned the diff lines for the gap between the deploy and that jump, and found only ordinary growth (about $194–$230/hour on case 5323).
- I can't see each case's status timestamps in the logs, so the mechanism is inferred from the code.

**Fix.** `min(timestamps)` is restored in `get_participant_role_time_seconds`, with a regression test, `test_case_cost_stops_at_earliest_status_timestamp`. It fails without the fix and passes with it.

**Clean-up still needed.** Stored costs for cases affected since 2025-09-02 must be recomputed, and finance needs to re-sync them. The scheduler skips stable cases it has already updated.

**Hourly TypeError.**
- **Cause:** `get_hourly_rate` divides the project's annual employee cost by its business-year hours. For one project the cost was `None`, so the division failed.
- **How NULL got in:** the project update API accepts null, and the column default only applies on insert.
- **Impact:** about 708 errors in `scheduler.log`, the first dated 2025-09-08. Each skipped the affected case's cost update every hour.
- **Fix:** the function now falls back to the Project model's defaults (50000 and 2080), with a test. Cases update on the next hourly run after deploy.
- **Still open:** `incident_cost/service.py` has the identical flaw, and the API can still write NULL.

**Status.** Both fixes and both tests are in the working tree, uncommitted and undeployed. `tests/case_cost`, `tests/incident_cost` and `tests/project` pass. I haven't run the rest of the suite.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost