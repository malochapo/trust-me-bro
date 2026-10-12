I fixed the weekday check and added a regression test; I haven't committed anything. The new test passes (3 cases). I didn't run the rest of the suite.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the check was never true. The close and stable reminders ran daily and never sent anything, with no error logged.

**Fix:** it now uses `date.today().weekday() == calendar.MONDAY`.

**Test:** `tests/case/test_case_scheduled.py` checks `_is_reminder_day()` on a Monday (2025-08-18, expects true), a Tuesday and a Sunday (expect false). The old code fails the Monday case.

**Triage-time bug not fixed:** the separate `NoneType` error in `case_close_reminder` still exists. Cases with no `triage_at` raise an error there, and it was still showing up in the logs after the deploy. I left it alone since it's a different bug. Say if you want it fixed too.

The deploy contents are inferred from git ancestry, since the logs only show the image tag.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18