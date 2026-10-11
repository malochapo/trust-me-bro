The weekly reminders stopped because of a refactor on 2025-08-12. The helper that gates them compares the wrong weekday numbering, so the Monday check is never true.

- **Before the refactor:** the close reminders for triage and stable cases went out on Monday 2025-08-11 (e.g. `scheduler.log:16803-16808`).
- **After it:** Monday 2025-08-18 has the daily triage and incident reminders, but no case close reminders.
- **The refactor:** commit `c509d45e` ("refactor(case): share the weekly reminder check") replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`. That helper compares `isoweekday()` (Monday = 1) against `calendar.MONDAY`, which is 0 in Python. I checked both values locally.

Because the check is never true, `q >= 1 and _is_reminder_day()` is always false in `case_close_reminder` and `case_stable_reminder`. The daily triage reminder doesn't use this helper, which is why it keeps working.

A fix would be to compare against `1`, or to use `calendar.MONDAY` with `date.today().weekday()`. I haven't changed the code.

Separately, the logs show `case_close_reminder` still raising `TypeError` on cases whose `triage_at` is `None` (`scheduled.py:47`), which the stable path already guards against. That doesn't cause this symptom, but it's worth fixing too.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It checks `date.today().isoweekday() == calendar.MONDAY`, but `isoweekday()` returns 1 for Monday while `calendar.MONDAY` is 0, so the weekly Monday gate is never true.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f