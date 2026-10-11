The weekly reminders stopped because the Monday check compares two different weekday numbering schemes, so it never matches.

`_is_reminder_day()` returns `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` numbers Monday as 1. `calendar.MONDAY` is 0, because the `calendar` module counts weekdays from Monday = 0. The comparison is therefore never true, and both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) skip every day, Mondays included.

The logs agree. "Case close reminder sent" appears on 2025-07-28, 08-04 and 08-11, all Mondays. It does not appear on 08-18 or any day after, and nothing in the code path logs the skip. The daily triage reminder never calls `_is_reminder_day()`, so it kept working.

Commit c509d45e (2025-08-12, "share the weekly reminder check") introduced it. It replaced the inline `isoweekday() == 1` in both functions with the shared helper. The first Monday after that commit, 08-18, had no reminders.

The `TypeError` entries in the scheduler log come from `case.triage_at` being `None` on some cases in `case_close_reminder`. They appear from 07-28 onward, before the regression, and each is caught per case. They are a separate, older problem and not why the reminders stopped.

I did not change any code.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the check is never true and the weekly close and stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f