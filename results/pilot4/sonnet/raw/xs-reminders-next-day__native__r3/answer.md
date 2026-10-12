Assignees stopped getting the Monday reminders because `_is_reminder_day()` compared the wrong numbering. The fix is in `src/dispatch/case/scheduled.py` and the new test passes.

**Cause:** `_is_reminder_day()` returned `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was true only on Sundays. The reminders run at 18:00 UTC and, in practice, never fired on a Monday.

**Origin:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the old inline `isoweekday() == 1` check into this helper. Both `case_close_reminder` (triage cases) and `case_stable_reminder` call it.

**Deploy and timing:** commit `c509d45e` is contained in commit `81d8ae42`. Both the scheduler and the web containers started on image `main-81d8ae42` on 2025-08-13 at 16:40Z. The scheduler log shows close reminders sent on Mondays 07-28, 08-04 and 08-11. There are none on 08-18, and the log ends on 08-20. I couldn't check the earlier image `main-b05613b5`: that commit isn't in this repo, so I'm inferring it predates the refactor from the date.

**Fix:** the helper now uses `date.today().weekday() == calendar.MONDAY`.

**Test:** `tests/case/test_case_scheduled.py` covers the helper on a Monday, Tuesday and Sunday. It also runs both reminder tasks with a case 10 days old and checks that a reminder is sent on a Monday but not on a Tuesday. All 5 tests pass with the fix. With the fix stashed, 3 of them fail (the Monday helper check and both task checks).

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18