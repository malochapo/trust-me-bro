The weekly close reminders stopped because of a Monday check that can never be true. It was added in the refactor `c509d45e` (Aug 12).

The refactor replaced `date.today().isoweekday() == 1` with a shared helper, `_is_reminder_day()`. That helper compares `isoweekday()` to `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, because the `calendar` module numbers weekdays from Monday = 0. I confirmed this in Python: `calendar.MONDAY` is 0 and 2025-08-18 has `isoweekday()` 1.

So `_is_reminder_day()` is now always false. Both `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) call it, so neither sends anything.

The logs fit this:
- **Aug 4 and Aug 11 (Mondays, before the refactor):** the scheduler sent "Case close reminder sent" 6 and 5 times.
- **Aug 18 (Monday, after the refactor):** it sent none. The run on pod `scheduler-mhtsgqwwx-q5q2n`, after the Aug 12 deploy, logs only a `triage_at` None error from the `case_close_reminder` job, and the other cases are skipped silently.
- **Daily triage reminders:** `case_triage_reminder` doesn't use the helper, which is why those kept arriving.

The `NoneType` errors in the logs, from `triage_at` or `stable_at` being unset on some cases, are present from Jul 28 onward. Each one is caught per case, so they are a separate nuisance rather than the cause.

The fix is to compare against `calendar.MONDAY + 1`, or to use `date.today().weekday() == calendar.MONDAY`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (= 0), so it is never true and the Monday-only close and stable reminders never send.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f