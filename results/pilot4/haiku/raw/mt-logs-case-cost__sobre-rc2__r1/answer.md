Here is the recap for the incident report.

**Summary**

- **Inflated case costs:** Commit `20f33137` (2025-09-02) changed the cost cut-off in `get_participant_role_time_seconds` from `min` to `max` over `stable_at`, `escalated_at` and `closed_at`. Participant time then ran until the latest of those timestamps rather than the earliest, so Stable and closed cases were overcharged. It shipped in `main-65f7df6e`, which rolled out to `dispatch-web` and `dispatch-scheduler` on 2025-09-02 at 18:14 UTC. The first anomalous jump is case 5284 on 2025-09-03 at 11:20 UTC; I found no anomalous jumps in the earlier hourly runs. Case 5363 went from 2261 to 6241 on 2025-09-09. Five cases were flagged in total.
- **Hourly TypeError:** `get_hourly_rate` divided `annual_employee_cost` by `business_year_hours`. A project whose `annual_employee_cost` was `NULL` raised a `TypeError` on each hourly run, starting 2025-09-08 15:55 UTC, so those cases got no cost. The logs don't name the project or show what cleared the value.
- **Fixes (uncommitted, in the working tree):**
  - Reverted `max` to `min` in `src/dispatch/case_cost/service.py`, with a regression test.
  - `get_hourly_rate` now falls back to the project model defaults (50000 and 2080, now named constants in `src/dispatch/project/models.py`) for missing values, with tests.
- **Not yet fixed:** `src/dispatch/incident_cost/service.py` has the same `get_hourly_rate` pattern. Finance also needs to re-run affected cases.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost