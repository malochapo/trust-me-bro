The weekday bug is fixed and covered by a regression test. The reminders should go out again on the next Monday the scheduler runs.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The comparison was always False, so no weekly reminder was ever sent. Both `case_close_reminder` and `case_stable_reminder` call this helper, so both were affected.

**Fix:** `date.today().weekday() == calendar.MONDAY`. `weekday()` is 0-based like `calendar.MONDAY`.

**Regression test:** `tests/case/test_case_scheduled.py` pins `date.today()` to each day of one week and checks `_is_reminder_day()` returns True only on Monday. The Monday case fails on the old code and passes on the fix. `python -m pytest tests/case` passes (22 tests). I did not run the full suite.

**Log evidence:** The Monday 2025-08-11 run was on image `main-b05613b5`, before the bug, and sent 5 close reminders. The first Monday on `main-81d8ae42` was 2025-08-18, and the logs show no reminder sends for it. The scheduler started on `main-81d8ae42` at 2025-08-13T16:40:06Z. The logs end around 2025-08-20, so I could not check later Mondays.

**Choices I made:**
- Fixed the helper rather than each caller, since both reminders share it.
- Left the project memory note saying "fix pending" unchanged. It is now stale.
- Did not commit. Changes are in the working tree: the one-line fix and the new test file.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18