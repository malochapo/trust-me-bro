The weekly reminders stopped because a refactor changed the Monday check so that it never matches.

On 2025-08-12, commit c509d45e ("share the weekly reminder check") moved the inline `date.today().isoweekday() == 1` test into a new helper, `_is_reminder_day()`. The helper compares `isoweekday()` with `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0. The comparison is therefore always false.

`case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) both gate on this helper, so neither sends anything any more.

The scheduler log fits this. "Case close reminder sent" lines appear on 2025-07-28, 08-04 and 08-11, which are the last Mondays before the refactor, and none after. The daily triage reminder doesn't use the helper, so it keeps arriving.

I didn't run the code. The diagnosis rests on the diff and the log pattern.

The older `NoneType` tracebacks in the scheduler log come from the `stable_at` bug that commit 32fa810f (#6179) already fixed. They are unrelated to this.

The fix is to compare against `calendar.MONDAY` using `date.today().weekday()`, or to compare `isoweekday()` with 1.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares date.isoweekday() (Monday is 1) with calendar.MONDAY (which is 0), so the check is never true and the weekly Monday reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f