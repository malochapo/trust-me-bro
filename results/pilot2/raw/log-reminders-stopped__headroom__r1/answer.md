Cause found: `calendar.MONDAY` is `0`, but `date.isoweekday()` returns `1` for Monday. The helper added in the Aug 12 refactor never matches, so the weekly branch never runs.

The timeline fits this:
- The last Monday reminders went out on 2025-08-11 (the Aug 11 run in scheduler.log shows "Case close reminder sent" lines), before the refactor commit `c509d45e` of Aug 12.
- On Monday 2025-08-18 the scheduler ran both jobs at 18:00 and sent no close or stable reminders.
- The daily triage reminder doesn't use `_is_reminder_day()`, so it kept arriving.
- The `NoneType` tracebacks in scheduler.log appear on days when reminders were still sent (for example 7/28 and 8/4), so they are unrelated noise.

The old inline check was `date.today().isoweekday() == 1`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (= 0), so it never returns True and the Monday-only close and stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f