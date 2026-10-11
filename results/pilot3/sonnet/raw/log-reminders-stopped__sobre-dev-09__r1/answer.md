The weekly reminders stopped because of a Monday check that can never be true. It was introduced by the refactor `c509d45e` (2025-08-12), which fits the mid-August start.

`_is_reminder_day()` replaced the inline test `date.today().isoweekday() == 1` with `date.today().isoweekday() == calendar.MONDAY`. `calendar.MONDAY` is 0, but `isoweekday()` returns 1 to 7, with Monday as 1. The comparison is therefore always false, and `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) never send anything.

Both functions call the helper, so they stopped together. The daily triage reminder doesn't use it, which is why it still arrives.

I did not compare the logs against the 2025-08-12 date. They do show a separate, older problem: `TypeError` errors on a `None` `triage_at` or `stable_at` in these two jobs from 2025-07-28 onward. The deployed code evidently predates the `stable_at` guard added in `32fa810f` (the traceback line numbers don't match the repo). That is not what stopped the Monday reminders, because the check above fails first.

The fix is to compare against `calendar.MONDAY + 1`, or use `date.today().weekday() == calendar.MONDAY`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (= 0), so the check is never true and the Monday close and stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f