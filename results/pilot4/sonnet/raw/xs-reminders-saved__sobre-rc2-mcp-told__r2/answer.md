Assignees stopped getting the weekly Monday reminders because `_is_reminder_day()` could never be true. I fixed it, and the new test passes with the fix and fails without it.

**Cause:** commit c509d45e (2025-08-12) moved the Monday check into `_is_reminder_day()`. It kept `date.today().isoweekday()`, which counts Monday as 1, but compared it to `calendar.MONDAY`, which is 0. The check was therefore false on every day, and `case_close_reminder` and `case_stable_reminder` never sent anything.

**Fix:** in `src/dispatch/case/scheduled.py`, the check now uses `date.today().weekday() == calendar.MONDAY`.

**Evidence from the scheduler log:**
- "Case close reminder sent" appears on the Mondays 2025-07-28, 08-04 and 08-11, and never after that.
- The scheduler pod restarted on image `main-81d8ae42` on 2025-08-13, and that image contains c509d45e.
- The previous image, `main-b05613b5`, does not contain it.
- The first Monday after the deploy was 2025-08-18.

**Test:** `tests/case/test_case_scheduled.py` has 9 tests. It checks that `_is_reminder_day()` is true only on Monday. It also runs the registered close and stable reminder tasks and checks they send on a Monday and not on a Tuesday. It uses mocks, so it needs no database. Without the fix, 3 of the 9 fail; the other 6 are the non-Monday cases, which pass either way.

I did not run the rest of the suite.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18