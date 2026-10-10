Root cause: the 8/12 refactor compares `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the check can never be true on a Monday.

The refactor is commit c509d45e. It replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`, which returns `date.today().isoweekday() == calendar.MONDAY`.

The logs fit this. Case close reminders went out on Mondays 7/28, 8/4 and 8/11. On 8/18, the first Monday after the refactor deployed, none were sent. The daily triage reminders don't use this check, so they kept arriving. The `NoneType` errors on `triage_at` and `stable_at` appear from 7/28 on, so they aren't the cause. A case with no `triage_at` is skipped, but other cases still get reminders.

Both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) call the helper, so both stopped. The fix is to compare against `calendar.MONDAY + 1` or use `date.today().weekday() == calendar.MONDAY`.

I didn't run the code or the tests. This is from reading the diff and the logs.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (which is 0), so it is never true on Mondays and the weekly triage and stable close reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f