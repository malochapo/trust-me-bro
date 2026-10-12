## Recap

**Incident 1: inflated case response costs.** Since the 2025-09-02 deploy, the hourly case-cost sync has recorded sudden jumps in response cost for Stable cases. Each case's cost climbed normally while it was active, then jumped once when it reached Stable, and then stayed flat. Five cases were flagged: 5284, 5327, 5264, 5363 and 5406. Case 5363 went from $2,261 to $6,241 on 2025-09-09.

- **Cause:** commit `20f33137` changed `min(timestamps)` to `max(timestamps)` in `get_participant_role_time_seconds`. That function sets the cut-off for a case's cost from its `stable_at`, `escalated_at` and `closed_at` timestamps. With `max`, a case whose escalation or closure time falls after its stable time keeps accruing cost up to that later time. The function's own comment specifies the earliest timestamp.
- **Shipped by:** image `main-65f7df6e` (which contains `20f33137`), rolled out to `dispatch-web` and `dispatch-scheduler` on 2025-09-02 at 18:14Z.
- **Fix:** restored `min`. Added `test_get_participant_role_time_seconds_cut_off_is_earliest_timestamp`, which fails with `max` and passes with `min`.

**Incident 2: hourly TypeError.** Since 2025-09-08 the case cost job has logged 708 `TypeError`s. Each one stops the cost update for one case in that run.

- **Cause:** `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours` without a null check. A project with `annual_employee_cost` unset raises the error.
- **Fix:** a missing value now falls back to the project model default, 50000 for the annual employee cost and 2080 for the business year hours. The defaults are named constants in `project/models.py`, used by the column defaults and by the fallback. Added two tests: one for the rate fallback, and one for a full case cost calculation on a project with no hourly inputs. Both fail on the original code.

**Test results:** the case-cost suite passes (22 tests). The full suite shows 8 failures in `tests/ai`, `tests/database` and `tests/entity`, and the same 8 fail on the original code.

**Not committed:** all changes are in the working tree on `main`. Nothing has been pushed.

**Open items:**
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division. Incident cost has one `TypeError` in the scheduler log, from the same kind of input. I did not change it.
- Case 5363's cost is flat from 2025-09-05 16:20Z to 2025-09-09 12:20Z, but it was reported as marked Stable on 09-09. The case's status history should confirm the timeline.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-03
MISSING_SETTING: annual_employee_cost