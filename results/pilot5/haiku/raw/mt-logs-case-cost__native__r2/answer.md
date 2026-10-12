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