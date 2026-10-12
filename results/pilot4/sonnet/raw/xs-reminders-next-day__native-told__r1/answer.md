The weekly reminders for long-running triage and stable cases should send again on Mondays. The new test passes with the fix and fails without it. I ran only `tests/case/test_case_scheduled.py`, not the full suite.

**Cause:** commit `c509d45e` (Aug 12) moved the Monday check into a shared helper, `_is_reminder_day()`. The helper compared `date.today().isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday but `calendar.MONDAY` is 0, so the check never passed. Both `case_close_reminder` (triage cases) and `case_stable_reminder` use the helper, so neither sent a reminder after the refactor.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`.

**Regression test:** the new file `tests/case/test_case_scheduled.py` checks `_is_reminder_day()` for a Monday, a Tuesday and a Sunday. It also runs both scheduled reminder functions on a Monday and a Tuesday with a case older than a week, and asserts the reminder is sent only on the Monday.

**Timeline from the logs:**
- Aug 11 was the last Monday the close reminders were sent.
- The scheduler and API both moved to image `main-81d8ae42` on Aug 13, 16:40 UTC. That image contains `c509d45e`.
- On Aug 18 at 18:00 the close and stable reminder jobs ran and sent nothing.

**Separate bug, not fixed:** the scheduler log shows `case_close_reminder` failing every day with `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` (`case.triage_at` is `None`). That predates this bug, since it appears in the July logs too, and the per-case `try` already catches it. It is probably still skipping those cases' reminders, so it needs its own look.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18