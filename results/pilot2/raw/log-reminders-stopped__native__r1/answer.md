The root cause is a day-numbering mismatch in a refactor that went out on 2025-08-12. It stopped the Monday reminders from ever being sent.

The helper `_is_reminder_day()` compares `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 (I checked in Python). `isoweekday()` never returns 0, so the check is always false. `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) both call it, so neither sends anything any more.

The logs fit this:
- **Last working Monday:** the scheduler logged "Case close reminder sent" on 2025-07-28, 08-04 and 08-11.
- **First broken Monday:** nothing was sent on 08-18, and the jobs still ran at 18:00 without errors from this check.
- **Triage reminders:** the daily `case_triage_reminder` doesn't use the helper, which is why those kept arriving.
- **Unrelated errors:** the `TypeError` traces (`datetime - None`) are old noise. They appear from 07-28, before the refactor, and were handled and logged without stopping the other cases.

The old code was `date.today().isoweekday() == 1`. The fix is to compare against `calendar.MONDAY + 1`, or to use `date.today().weekday() == calendar.MONDAY`, since `weekday()` numbers Monday as 0. I haven't made the change.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (= 0), so it is never true and the weekly Monday reminders for triage and stable cases are silently skipped.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f