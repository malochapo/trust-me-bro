I fixed the weekday check in `src/dispatch/case/scheduled.py` and added a regression test. The new test passes (3 cases). I didn't run it against the old code, but it would have failed there: `isoweekday()` returns 1 on Mondays and the code compared it to `calendar.MONDAY`, which is 0.

- **Cause:** `_is_reminder_day()` compared `isoweekday()` to `calendar.MONDAY`, so it was never true and the weekly close reminders never went out. `case_triage_reminder` doesn't use it, which is why the daily triage reminders kept working.
- **Fix:** it now uses `date.today().weekday() == calendar.MONDAY`.
- **Test:** `tests/case/test_case_scheduled.py` checks that Monday 2025-08-18 counts as a reminder day and that Tuesday 2025-08-19 and Sunday 2025-08-24 don't.
- **Not committed:** the change is in the working tree only.
- **Stable reminder:** my notes mention a `case_stable_reminder` that uses this check, but I found no such function in the file. Only `case_close_reminder` calls `_is_reminder_day()` here. I didn't look for where stable-case reminders live now.
- **Left alone:** `case_close_reminder` still raises `TypeError` for triage cases where `triage_at` is None. It's caught per case, and I didn't add a guard.

The deploy details come from my saved notes from yesterday's log investigation; I didn't re-check the logs. The old image's last Monday send was 2025-08-11, and the 2025-08-18 run sent nothing.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18