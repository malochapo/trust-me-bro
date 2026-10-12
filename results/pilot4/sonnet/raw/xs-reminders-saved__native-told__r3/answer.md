I fixed the bug. `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()`, where Monday is 1, to `calendar.MONDAY`, which is 0. The check could never be true, so `case_close_reminder` and `case_stable_reminder` never sent anything. It now uses `weekday()`, where Monday is 0.

I added `tests/case/test_case_scheduled.py`. It checks a Monday, a Sunday, a Tuesday and a Wednesday. The four cases pass with the fix. With the old code, the Monday case fails, so the test would have caught the bug. I did not run the rest of the suite.

The logs confirm what my memory notes said. Both production images started on 2025-08-13 at 16:40Z, and `main-81d8ae42` includes the bad commit `c509d45e`. On Monday 2025-08-18 the scheduler sent no case close reminders, compared with 6 on 08-04 and 5 on 08-11.

I left alone the separate `TypeError` in `case_close_reminder` when `triage_at` is null. It is unrelated to this bug.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18