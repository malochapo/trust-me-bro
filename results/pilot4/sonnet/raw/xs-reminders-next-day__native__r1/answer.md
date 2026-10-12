I fixed the bug and added a regression test. The test fails on the old code and passes on the fix.

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. The close and stable reminders in `src/dispatch/case/scheduled.py` both call it, so neither fired again. I changed it to `weekday()`, which matches `calendar.MONDAY`.

**Test:** `tests/case/test_case_scheduled.py` checks that a Monday returns True and a Tuesday and a Sunday return False. It only covers `_is_reminder_day()`, not the two reminder jobs themselves. I ran only that file, not the full suite.

**Timeline:**
- Commit `c509d45e` ("share the weekly reminder check", Aug 12) introduced the bug. It replaced the inline `isoweekday() == 1` with the helper.
- The scheduler image `main-81d8ae42` shipped it. That commit contains `c509d45e`, and the scheduler started on that image on 2025-08-13 at 16:40Z.
- The scheduler log shows close reminders sent on Jul 28, Aug 4 and Aug 11, and none on Aug 18.

**Not fixed:** the logs also show a repeated error, `datetime - NoneType`, at `case.triage_at` in `case_close_reminder` (line 47 on Aug 18). It predates the weekday bug, and the per-case `try/except` stops it blocking other cases. I left it alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18