Recap for the incident report:

**Inflated case costs.** Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function sets the cut-off for a participant's time in a case, which should be the earliest of stable, escalated or closed. With `max`, the cut-off moved to the latest of those events, so time was billed after the case had stabilised or escalated. The code comment says "earliest", and the existing test only covered `stable_at`, so CI didn't catch it. The commit shipped in build `main-65f7df6e`, rolled out on 2025-09-02 at 18:14. The first clearly inflated cost is case 5284 on 2025-09-03 (3331 → 8804, +5473 in one hour). The pre-deploy hourly delta has a median of 97 and a maximum of 221. Case 5323 on 2025-09-02 19:20 rose by 230, which is within normal variation for a high-cost case, so I didn't count it. The logs don't include the case timestamps, so the per-case mechanism is inferred from the code and not yet confirmed against Dispatch's database. The fix (revert to `min`) and a regression test are in the working tree, not committed.

**Hourly TypeError (separate bug).** Since 2025-09-08 15:55, `get_hourly_rate` in the same file has divided `annual_employee_cost` by `business_year_hours` without a `None` check. That raised a TypeError for 708 cases, which the scheduler caught and skipped, so those cases got no cost. Missing values now fall back to the `Project` column defaults (50000 and 2080), with a test. I haven't confirmed how the NULLs were written, and the logs don't name the affected projects. The same unguarded function exists in `incident_cost/service.py`, which I left unchanged.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost