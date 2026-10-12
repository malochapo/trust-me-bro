## Recap

**Cost inflation.** On 2025-09-02, commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function sets the cut-off time at which a case stops accruing cost. The comment above it, and the earlier behaviour, call for the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, a case that was escalated and later marked stable or closed kept accruing cost for the whole gap. The inflated cost then reached the warehouse on the next hourly sync. The change shipped to production in image `main-65f7df6e`, rolled out from 2025-09-02 18:14Z.

The first inflated cost I can see is case 5284 on 2025-09-03 at 11:20Z, which went from 3331 to 8804. In the sync window between the deploy and that run, no other case rose by more than $400. A smaller inflated case in that window can't be ruled out entirely. Later flagged cases were 5327, 5264, 5363 and 5406.

**Hourly TypeError.** Since 2025-09-08 15:55, the scheduler's hourly case cost job logged 708 TypeErrors. `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`, and those project columns are nullable, so a project missing either one failed. The error handling is per case, so those cases silently got no cost update. We don't know which projects have NULLs or why it started on 09-08.

**Changes in the working tree (not committed):**
- Reverted `max` to `min`, with a regression test.
- `get_hourly_rate` now falls back to the `Project` model defaults (50000 and 2080), with tests.

**Follow-ups:**
- Backfill the warehouse rows for stable or closed cases written since 2025-09-02 18:14Z.
- The same unguarded division exists in `incident_cost/service.py`.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost or business_year_hours (the project's annual employee cost / business year hours)