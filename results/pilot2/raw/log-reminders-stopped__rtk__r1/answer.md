The weekly reminders stopped because a refactor changed the Monday check so it can never be true.

Commit c509d45e moved the original `date.today().isoweekday() == 1` check into a shared helper, `_is_reminder_day()`. The helper compares `isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0. The comparison is therefore never true.

Both `case_close_reminder` and `case_stable_reminder` call the helper, so both silently stop sending. Neither logs anything when it skips. The daily triage reminder doesn't use the helper, which is why it kept working.

I did not trace the logs for the mid-August date. The only link is that the refactor is dated 2025-08-12.

The `TypeError` entries in `scheduler.log` are a separate, earlier problem. They come from cases with a missing `stable_at` or `triage_at`, and 32fa810f partly fixed that on 2025-08-11. The fix is to compare against 1, or use `date.today().weekday() == calendar.MONDAY`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the check is never true and the weekly close and stable reminders are never sent.
INTRODUCED_BY: c509d45e