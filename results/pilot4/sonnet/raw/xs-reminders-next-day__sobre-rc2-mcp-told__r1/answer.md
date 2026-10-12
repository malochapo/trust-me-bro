Weekly close reminders for triage and stable cases work again. The new test passes with the fix and fails on the Monday case without it.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` counts Monday as 1, but `calendar.MONDAY` is 0, so the check was never true and no Monday reminder was sent. Commit c509d45e (2025-08-12) introduced it when it replaced the inline `isoweekday() == 1` check with a shared helper.

**Fix:** the helper now uses `date.today().weekday() == calendar.MONDAY`. Both `weekday()` and `calendar.MONDAY` use 0 for Monday.

**Test:** `tests/case/test_case_scheduled.py` checks that a Monday returns true and that Tuesday, Saturday and Sunday return false. I did not run the rest of the suite.

**Logs:**
- Reminders went out on 2025-07-28, 08-04 and 08-11.
- The first deploy after the bad commit was image `main-81d8ae42` on 2025-08-13, and 81d8ae42 descends from c509d45e.
- The 08-18 scheduler run logged no "Case close reminder sent" lines, while the triage and incident reminders still ran.

I left one separate problem alone. `case_close_reminder` also logs `datetime - NoneType` errors on many days, including before the regression, because some triage cases have a null `triage_at`. That error is caught per case, but it skips those cases, so you may want a follow-up fix.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18