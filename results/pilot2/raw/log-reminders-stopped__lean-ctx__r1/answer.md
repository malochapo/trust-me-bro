The weekly Monday reminders stopped because a refactor changed how "is it Monday" is checked, and the new check can never be true.

The refactor, commit c509d45e (Aug 12), moved the check `date.today().isoweekday() == 1` into a shared helper `_is_reminder_day()`. The helper compares `isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0. The comparison is therefore false every day.

Both `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) now call this helper. Neither sends its weekly reminder any more. The daily triage reminder, `case_triage_reminder`, doesn't use the helper, so it keeps working. No error is logged, which is why nothing looked wrong.

I found this by reading the code and the commit diff. I didn't confirm from the logs that the Monday reminders stopped after Aug 12. The scheduler log also shows a separate, older error in `case_stable_reminder` on 2025-07-28 and 2025-08-11 (`datetime - None`). That error comes from cases with no `stable_at`, which is a different problem.

The fix is to compare against `calendar.MONDAY + 1`, or use `date.today().weekday() == calendar.MONDAY`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `isoweekday()` (Monday = 1) with `calendar.MONDAY` (= 0), so it is never true and the weekly close and stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f