**Recap**

- **Weekly reminders stopped.** The weekly close and stable reminders for long-running cases stopped going out after the 2025-08-13 deploy. The daily triage reminders kept working.
- **Root cause.** Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. It compares `date.today().isoweekday()`, where Monday is 1, to `calendar.MONDAY`, which is 0. The check was always false.
- **Deploy.** Image `main-81d8ae42` started on 2025-08-13 at 16:40 UTC. It is the first deploy that contains the refactor. The Monday 2025-08-18 run sent no close reminders, while the earlier Mondays did.
- **Fix.** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. A regression test in `tests/case/test_case_scheduled.py` pins the date to Monday, Tuesday and Sunday, and it fails on the old code.
- **Evening TypeError.** `case_close_reminder` subtracted `triage_at`, which is NULL for some triage cases. Those cases can be created directly in triage, or moved into triage from Stable or Escalated, without the flow that sets `triage_at`. The fix counts from `created_at` when `triage_at` is missing. Two tests cover the fallback and the precedence of `triage_at`. The root cause in those paths is still open.
- **Tests.** The full suite has 8 failures that also occur without these changes. They are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`.
- **Not committed.** The changes are in the working tree.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at