The weekly Monday reminders are fixed. The new tests pass with the fix and fail without it.

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` counts Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. Commit c509d45e refactored the inline `isoweekday() == 1` check into this helper and introduced the mismatch. The helper is shared by `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases), so both stopped sending.

**Fix:** the helper in `src/dispatch/case/scheduled.py` now uses `weekday()`, which is 0 for Monday.

**Regression test:** `tests/case/test_case_scheduled.py` has 11 tests. They check that:
- `_is_reminder_day()` is true only on a Monday.
- Both the triage and stable reminder tasks send on a Monday and don't send on a Tuesday, for cases older than a week.

**Evidence from the scheduler log:**
- Close reminders were sent on Mondays 2025-07-28, 08-04 and 08-11.
- The scheduler on image `main-81d8ae42` started on Wed 2025-08-13, and c509d45e is in that image but not in the earlier `main-b05613b5`.
- No reminders went out on Monday 2025-08-18.
- The scheduler log's error lines (a `NoneType` subtraction in the same two task functions) predate the refactor, so they aren't the cause.

I did not run the full suite, only the new test file.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18