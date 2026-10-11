The root cause is a refactor that swapped `isoweekday() == 1` for a comparison against `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the new check is true only on Sundays.

The logs fit that. Case close reminders went out on Monday 2025-08-04, with 11 sent that day, and on Monday 2025-08-11, with 5 sent. None went out on Monday 2025-08-18. The refactor was committed on 2025-08-12, so the first Monday it affected was 08-18. The scheduler's 18:00 job only sends these reminders when `_is_reminder_day()` is true, and it is never true on a Monday now.

The daily triage reminders don't use this check, which is why they still arrive. I didn't confirm Sunday sends in the log, and I didn't run the code.

The `TypeError` tracebacks in the scheduler log are caught and logged per case. They predate the change and are not the cause.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (= 0), so the weekly close/stable reminders fire only on Sundays and never on Mondays.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f