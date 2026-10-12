## Recap

**Cost inflation:**
- Commit `20f33137` (merged Sept 2, 09:29 PDT) changed the cost cut-off in `get_participant_role_time_seconds` from `min(timestamps)` to `max(timestamps)`.
- The cut-off is meant to be the earliest of `stable_at`, `escalated_at` and `closed_at`. With `max`, cases that were stable, escalated or closed kept accruing cost past that point.
- Image `main-65f7df6e` was the first production deploy after that commit. It rolled out on Sept 2 at about 18:14 UTC.
- The first inflated cost I found in the cost-sync log is case 5284 (dispatch-default-security-5284), at the 2025-09-03 11:20 UTC sync (3331 → 8804). I filtered the sync log for large single-sync jumps between the deploy and that sync and found only this one. I did not rule out smaller inflation in that window.
- The other flagged cases followed on Sept 5, 8, 9 and 12.
- Fix: `min` is restored, plus a regression test that sets `stable_at` together with a later `closed_at` or `escalated_at`.

**Hourly TypeError (since Sept 8):**
- `get_hourly_rate` in the same file divides `annual_employee_cost` by `business_year_hours`. Both are nullable project settings, and the model defaults only apply on insert.
- A project with a NULL value made the division fail with `NoneType / int`, and those cases got no cost.
- Fix: a missing value now falls back to the `Project` model default. Tests were added.
- The logs don't show what left the setting empty from Sept 8, so that is still open.
- `incident_cost/service.py` has the same unguarded `get_hourly_rate`. It is unchanged.

**Open items:** the code changes are uncommitted and not deployed. Warehouse costs for cases that went stable, escalated or closed since Sept 2 need recalculating and re-syncing.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137
DEPLOYED_IMAGE: registry.example.com/dispatch:main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost or business_year_hours