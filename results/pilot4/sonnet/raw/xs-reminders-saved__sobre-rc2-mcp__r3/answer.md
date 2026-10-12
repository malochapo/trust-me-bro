The weekly close and stable reminders now go out on Mondays again. I haven't committed anything.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0. The check was never true, so `case_close_reminder` and `case_stable_reminder` skipped every case. Jordan Lee introduced it in `c509d45e` on 2025-08-12. It shipped in image `main-81d8ae42`, which went live on 2025-08-13 around 16:40Z. I rechecked the deploy time in the logs; the rest of the cause and the Monday evidence are from my notes from yesterday.

**Fix:** the helper now uses `date.today().weekday() == calendar.MONDAY`.

**Test:** `tests/case/test_case_scheduled.py` checks the helper on all seven days of a week, true only on Monday. The new test passes with the fix. With the fix stashed, the Monday case fails (the other six days pass). I ran only this file, not the full suite.

I did not change the `datetime - NoneType` errors for cases with a missing `triage_at` or `stable_at`. They predate the deploy and are caught per case, so they didn't cause the outage.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18