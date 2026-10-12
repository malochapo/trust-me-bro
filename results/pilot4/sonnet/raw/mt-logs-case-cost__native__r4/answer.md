## Recap

**Cost inflation**
- Commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds()`. That function sets the point where a case's participant time stops counting. The cut-off moved from the earliest of `stable_at`, `escalated_at` and `closed_at` to the latest. A case that was marked stable and later closed or escalated therefore kept accruing cost for the whole gap.
- The change reached production in image `dispatch:main-65f7df6e` on 2025-09-02 at about 18:14–18:15Z, when both the web and scheduler deployments rolled. The affected code is in the scheduler's hourly job.
- Cost-sync flagged five Stable cases for jumps of 147–265%, starting with case 5284 on 2025-09-03. Case 5363 was the 2261 → 6241 jump on 09-09.
- The 09-03 date is the earliest large jump in the sync log. I only checked for jumps over $600, so smaller inflations before that are possible. Because the stored costs are still wrong, they need a backfill. The fix is in the working tree and not committed or deployed.

**Hourly TypeError**
- The project's `annual_employee_cost` was NULL, so `get_hourly_rate()` divided `None` by an int. The error is logged per case and the loop continues, so those cases got no cost update.
- `get_hourly_rate()` now falls back to the project model defaults (50000 and 2080) for whichever value is missing.

**Changes, uncommitted**
- `src/dispatch/case_cost/service.py`: `min` restored, and the hourly-rate fallback added.
- `src/dispatch/project/models.py`: the default values are now named constants.
- `tests/case_cost/test_case_cost_service.py`: three regression tests, which fail on the old code.

**Open items**
- Backfill and re-sync the costs of every Stable, Escalated or Closed case touched since 2025-09-02 18:15Z.
- Find the project with NULL cost settings and fix its data.
- `incident_cost/service.py` has the same unguarded division.
- Nothing in the logs shows when the NULL value first appeared, but the errors begin 2025-09-08 15:55.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost