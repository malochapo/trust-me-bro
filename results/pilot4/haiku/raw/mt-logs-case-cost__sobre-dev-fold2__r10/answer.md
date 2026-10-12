## Recap

**Cost inflation (the classic cost jump).** Commit `20f33137` (Sep 2, "fix(case_cost): use the latest status timestamp as the cost cut-off") changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function picks the cut-off for participant time from a case's `stable_at`, `escalated_at` and `closed_at`. With `max`, participant time runs to the latest milestone instead of the first, which inflates hours and classic cost. The function's docstring and comment say "earliest", so I treated the commit as the mistake. Its title says "latest", so the author should confirm the intent. The fix restores `min`, and a regression test fails with `max` and passes with `min`.

The bug shipped in image `main-65f7df6e`, rolled out to `dispatch-web` and `dispatch-scheduler` on 2025-09-02 at 18:14 UTC. The scheduler restarted onto it at 18:15:30. Later images (`main-51546e13`, and the Sep 10 scheduler restart) still ran the `max` code, and HEAD had it until my fix.

**Hourly TypeError.** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. When the project's `annual_employee_cost` is `NULL`, the division raises a `TypeError`, which aborts the whole case's cost calculation, classic cost included. The fix uses the project model's column defaults (50000 and 2080) for any unset value. Two new tests cover this; both fail against the old code and pass with the fix.

**Not verified:**
- The case-5363 jump on Sep 9 (2261 → 6241) fits the `max` mechanism, but the logs have no per-case milestone timestamps, so I could not confirm it.
- The logs show no clean break in total classic cost at the rollout, so I could not confirm the size of the effect across all cases.
- `FIRST_INFLATED` below is the rollout date, not a verified first inflated case.
- `incident_cost/service.py:131` has the same `get_hourly_rate` bug and is not fixed.

**Open items:** nothing is committed. The warehouse rows written since Sep 2 need a backfill, which is a decision for finance.

```
FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-02
MISSING_SETTING: annual_employee_cost
```