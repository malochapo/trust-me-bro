Fixed the weekday check, and `_is_reminder_day()` now returns true on Mondays. I also added a regression test.

**Cause:** commit `c509d45e` made `_is_reminder_day()` compare `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. Both the triage close reminder and the stable reminder depend on it, so neither was sent. The daily triage reminder doesn't use it, so it kept working.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`, where Monday is 0 on both sides.

**Test:** `tests/case/test_case_scheduled.py` checks a Monday, a Tuesday and a Sunday. It has not been run against the old code to confirm it fails there. The three cases pass with the fix.

**Timeline from the logs:** the image `main-81d8ae42`, which contains `c509d45e`, started on both the scheduler and web pods on 2025-08-13 at 16:40Z. The Monday before (2025-08-11) still sent reminders, and 2025-08-18 was the first Monday with none.

The `TypeError` on `case.triage_at` in `case_close_reminder` that I noted earlier is still there. It was logging before the deploy too, so it isn't what stopped the reminders, and I didn't touch it.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18