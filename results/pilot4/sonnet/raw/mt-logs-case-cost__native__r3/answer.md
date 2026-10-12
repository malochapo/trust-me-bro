**Recap**

- **Symptom:** from early September, the case costs that case-cost-sync copied into the finance warehouse jumped by several times in a single hourly step. The example case was dispatch-default-security-5363, which went from $2,261 to $6,241 on September 9.
- **Root cause:** commit `20f33137` changed the cost cut-off in `get_participant_role_time_seconds` from `min(timestamps)` to `max(timestamps)`. The timestamps are `stable_at`, `escalated_at` and `closed_at`. A case with more than one of them was then costed through the latest one instead of the earliest.
- **Deploy:** the commit went to production in `main-65f7df6e`, which reached the scheduler on 2025-09-02 at 18:15Z. The later deploy `main-51546e13` (09-04) and the case-cost-sync 1.5.0 upgrade (09-01) don't explain the jumps.
- **Evidence:**
  - Before the deploy, the sync logs show no flagged cases.
  - Afterwards there are five large jumps, all on Stable cases: 5284 on 09-03, 5327 on 09-05, 5264 on 09-08, 5363 on 09-09 and 5406 on 09-12.
- **Fix:** I reverted the cut-off to `min` and added `test_case_cost_stops_at_earliest_status_timestamp`. It fails on the `max` code and passes on `min`.
- **Still to do:** deploy the fix, then backfill cases that went stable or escalated since 09-02 18:14Z, then re-sync the warehouse.
- **Unconfirmed:** the logs don't hold case timestamps, so the exact trigger for each jump isn't shown. A query on those cases' timestamp columns would confirm it. `FIRST_INFLATED` is also only the first large jump visible in the sync logs. Smaller inflation on other cases could have started earlier. I did check the window from the deploy to that jump and found nothing else out of the ordinary.
- **Separate issue:** from 09-08 the hourly job logged 708 `TypeError`s, all from `get_hourly_rate` dividing a NULL `annual_employee_cost`. It now falls back to the `Project` model defaults, with a new test. `incident_cost/service.py` has the same weakness and is not fixed. The logs don't show which project is affected or what set the value to NULL.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost