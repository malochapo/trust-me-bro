That +230 on case 5323 is ordinary growth from a participant joining, not this bug, so the first inflated case is 5284 on Sep 3.

## Recap

**Cost inflation.**
- **Cause.** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function sets the point where a case's response cost stops accruing, using `stable_at`, `escalated_at` and `closed_at`. With `max`, a case that has more than one of those timestamps keeps accruing cost up to the latest one instead of stopping at the earliest.
- **Deploy.** The change first reached production in `main-65f7df6e` on Sep 2 at about 18:14Z. `main-51546e13` on Sep 4 also contains it.
- **First inflated case.** Case 5284 was inflated on Sep 3 (3331 → 8804 at 11:20Z). Before the deploy, nothing was flagged. The other flagged cases were 5327 (Sep 5), 5264 (Sep 8), 5363 (Sep 9) and 5406 (Sep 12).
- **Fix.** I reverted the line to `min` and added `test_case_cost_stops_at_earliest_status_timestamp`. It fails without the fix.
- **Not yet done.** Warehouse rows written since Sep 2 18:15Z are still inflated. Stable cases whose cost was already updated after `stable_at` won't be recomputed by the scheduler, so they need a one-off recalculation and re-sync.

**Hourly TypeError.**
- **Cause.** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`, and one was `None` for the new `fraud` project. The project API allows null for both, and an explicit null bypasses the column defaults (50000 and 2080). The scheduler first logged the error on Sep 8 at 15:55. I inferred `fraud` is the affected project from the log timing, not from its stored values.
- **Fix.** `get_hourly_rate` now falls back to the `Project` model defaults for whichever value is missing, with a test.
- **Open item.** `incident_cost/service.py:133` has the same division and would fail the same way. I left it unchanged.

Both fixes are uncommitted in the working tree.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost