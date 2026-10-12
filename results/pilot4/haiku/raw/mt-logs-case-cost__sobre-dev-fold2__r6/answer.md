The first hourly run after the rollout is at 18:20Z on Sep 2, four minutes after the image went out. The logs don't show each case's status timeline, so I can't prove that run's changes came from this bug. I'll use Sep 2 as the first inflated date and flag that.

## Recap: case cost inflation and the hourly TypeError

**Symptom.** Since early September, finance's warehouse has received case response costs several times higher than before. Dispatch's hourly scheduler job also logs a `TypeError` for a few cases each hour, starting Sep 6 and running steadily from Sep 8.

**Root cause 1: the cost cut-off used the latest status timestamp.** Commit `20f33137` (Sep 2) changed `min` to `max` when picking the participant-role cut-off from `stable_at`, `escalated_at`, and `closed_at`. The function's own comment calls for the earliest of these. With `max`, participants kept accruing cost until the last status change, so a case that was escalated and later stable or closed was charged for the gap. The image `main-65f7df6e` shipped it to production on Sep 2 at 18:15Z. The fix changes `max` back to `min`, with a regression test that fails on the old code (`10800.0 == 3600`).

**Root cause 2: unguarded hourly rate.** `get_hourly_rate` divides `annual_employee_cost` by `business_year_hours`. A project whose `annual_employee_cost` is `NULL` raises `TypeError: unsupported operand type(s) for /: 'NoneType' and 'int'`. The scheduler logs the error and skips the case, so those cases were missing costs. The fix substitutes the project model's defaults (`50000` and `2080`, now named constants in `project/models.py`) for missing values, with tests for each missing-value combination and for the full cost path. I have not confirmed which code path writes the `NULL`s.

**Verification.** `python -m pytest` passes on the case, case-cost, case-cost-type, project, and incident-cost test suites (65 tests). The new tests fail on the old code. Nothing is committed.

**Open items:**
- The warehouse still holds inflated `case_response_cost` rows from Sep 2 onward. The fix doesn't correct them, so finance needs a backfill.
- `src/dispatch/incident_cost/service.py:133` has the same unguarded division, so the incident cost job may hit the same `TypeError`. I didn't change it.

FILE: src/dispatch/case_cost/service.py
FUNCTION: get_participant_role_time_seconds
INTRODUCED_BY: 20f33137d520c7472bf9f634b29b730bd83f860e
DEPLOYED_IMAGE: main-65f7df6e
FIRST_INFLATED: 2025-09-02
MISSING_SETTING: annual_employee_cost