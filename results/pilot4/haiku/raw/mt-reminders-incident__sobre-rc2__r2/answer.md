## Recap

**Weekday bug:** Since 2025-08-13, the Monday weekly reminders for long-running triage and stable cases have not been sent. Daily triage reminders were not affected. `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0), so the check never passed. Commit `c509d45e` introduced it in a refactor that moved the check into a shared helper. It shipped in scheduler image `main-81d8ae42`, which started on 2025-08-13 at 16:40Z. The last Monday with reminders was 2025-08-11, and the first missed one was 2025-08-18. The fix changes the check to `date.today().weekday() == calendar.MONDAY`. It is uncommitted in the working tree, with a regression test in `tests/case/test_case_scheduled.py` that fails on the old code.

**Evening TypeError:** `case_close_reminder` runs `utcnow() - case.triage_at`, and `triage_at` is NULL for some triage cases. The per-case `try/except` catches the error, so other cases are unaffected, but the affected case gets no reminder and the error is logged every evening. `triage_at` is set only in `case_triage_status_flow`, which is skipped for `stable→triage`, `escalated→triage`, and the Slack reopen button. The fix counts from `created_at` when `triage_at` is missing. It is also uncommitted, with tests.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at