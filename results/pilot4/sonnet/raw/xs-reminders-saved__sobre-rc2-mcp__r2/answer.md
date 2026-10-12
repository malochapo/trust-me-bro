Fixed. The weekly Monday close and stable reminders were never sent because `_is_reminder_day()` compared `isoweekday()`, which runs 1–7, to `calendar.MONDAY`, which is 0. It could never be true.

- **Fix:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` now compares `weekday()` (0-based) to `calendar.MONDAY`. It also takes an optional date so it can be tested.
- **Regression test:** `tests/case/test_case_scheduled.py` checks the helper is true only on a Monday, and that it defaults to today. All 8 tests pass with the fix and all 8 fail without it. I did not run the rest of the suite.
- **Not changed:** the `triage_at` None guard in `case_close_reminder`, which causes the daily NoneType errors but not this bug. I left it out because you didn't ask for it.

The commit `c509d45e` reached production in image `main-81d8ae42`, deployed 2025-08-13 16:40Z. The scheduler logs show the last close reminders on Monday 2025-08-11, so 2025-08-18 was the first Monday missed.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18