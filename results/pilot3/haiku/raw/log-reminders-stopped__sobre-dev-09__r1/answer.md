The root cause is in `_is_reminder_day()`, added by commit `c509d45e` on Aug 12. It compares `isoweekday()` (Monday = 1) against `calendar.MONDAY`, which is 0 in Python's `calendar` module. The check is never true, so the weekly close and stable reminders are never sent. The daily triage reminder doesn't call this helper, which is why it still arrives.

I confirmed the constants directly: `calendar.MONDAY` is 0 and `date(2025, 8, 11).isoweekday()` is 1. The refactor replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`, so the value that used to be 1 became 0. Before that commit the comparison was correct, and the Monday after Aug 12 is the first one where the reminders would have been skipped.

I did not find the missing reminders in the logs themselves. The scheduler log shows only per-case debug and error lines, not sent reminders, so the diagnosis rests on the code and the commit. The fix is to compare against `1`, or to use `calendar.MONDAY + 1`, or to compare `date.today().weekday() == calendar.MONDAY` (`weekday()` is 0-based like `calendar.MONDAY`). I have not changed the code or added a test.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0), so the weekly Monday check is never true and the long-running triage and stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f