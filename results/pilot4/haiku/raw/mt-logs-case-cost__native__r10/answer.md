Here's the recap for the incident report.

**Incident: inflated case response costs (from Sep 3) and skipped cases (from Sep 8)**

1. **Inflated costs.** Commit `20f33137` (Sep 2) changed the case-cost cut-off from the earliest milestone (`min`) to the latest (`max`) of `stable_at`, `escalated_at` and `closed_at`. Once a case was escalated, its cost froze at the escalation time. When the case was later marked stable, the cut-off moved to `stable_at`, so the cost jumped. Case 5363 went from 2261 to 6241 on Sep 9 this way. The change reached production in `main-65f7df6e` on Sep 2 at 18:14 UTC. The first flagged inflation was case 5284 on Sep 3 at 11:20 UTC.
2. **Hourly TypeError.** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours` with no null check. Projects with no annual employee cost set raised a TypeError, and the scheduler logged it and skipped the case. The log shows 708 of these from Sep 8 onward.

**Fixes (not committed):**
- `src/dispatch/case_cost/service.py`: the cut-off is back to `min`. `get_hourly_rate` falls back to the project model defaults for a missing value.
- `src/dispatch/project/models.py`: the defaults (50000 and 2080) are now shared constants used by the column defaults, the Pydantic schema and the fallback.
- Tests: `test_case_cost_stops_at_first_milestone_when_escalated_then_stable` fails with the `max` change and passes with the fix. `test_get_hourly_rate_uses_project_defaults_when_values_missing` covers each missing value.
- `python -m pytest tests/project tests/incident_cost tests/case_cost`: 42 passed.

**Open items:**
- Costs written with the bad cut-off, and cases skipped since Sep 8, aren't corrected. The finance team will need a backfill.
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division. I didn't change it.
- I couldn't explain the 3425 → 1243 drop for case 5363 on Sep 5.
- I couldn't identify the projects with null settings, because the logs don't name them.
- Ruff wasn't available, so the changes weren't linted.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost