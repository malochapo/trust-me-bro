I fixed the weekday bug, and the new tests pass with the fix. With the fix reverted, the two Monday cases fail, so they would have caught it.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the check was never true. That silenced the weekly close reminders for triage cases and the weekly reminders for stable cases. The daily triage reminder doesn't use the check, so it kept working.

**Fix:** the check now uses `date.today().weekday() == calendar.MONDAY`.

**Test:** `tests/case/test_case_scheduled.py` checks that `_is_reminder_day()` is true on Monday 2025-08-18 and false on a Tuesday and a Sunday. It also runs the real close and stable reminder tasks with the date mocked and confirms they send on a Monday and don't on a Tuesday.

**Log check:** I re-checked the logs. "Case close reminder sent" appears on 2025-07-28, 08-04 and 08-11 and never on 08-18. Image `main-81d8ae42` started on 2025-08-13T16:40Z in both the scheduler and the API.

I didn't touch the separate bug I noted earlier: `case_close_reminder` subtracts `case.triage_at` without a `None` check, so cases with no `triage_at` raise a `TypeError`. The per-case `try`/`except` catches it and logs it, so other cases still get their reminders. I haven't committed anything.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18