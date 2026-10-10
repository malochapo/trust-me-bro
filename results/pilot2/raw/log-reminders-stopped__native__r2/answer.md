The cause is the Aug 12 refactor, which changed the Monday check so it can never be true.

Before it, both reminders checked `date.today().isoweekday() == 1`. The refactor replaced that with a shared helper, `_is_reminder_day()`, in `src/dispatch/case/scheduled.py`. The helper compares `date.today().isoweekday()` to `calendar.MONDAY`. `calendar.MONDAY` is 0, because the `calendar` module numbers weekdays from 0 (Monday) to 6. `isoweekday()` returns 1 to 7, with Monday as 1. The comparison is therefore never true on any day.

Both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) gate their weekly send on that helper, so neither fires any more. `case_triage_reminder` doesn't call it, which is why the daily triage reminders still arrive.

I didn't confirm from the logs that the reminders actually stopped. I only read the code and the commit diff, and the `calendar.MONDAY` value is from my knowledge of Python's `calendar` module, not something I ran. The logs show a separate, older problem: `TypeError` tracebacks from `case.triage_at` being `None` in `case_close_reminder`, one per day from 2025-07-28 through 2025-08-11. I haven't traced why they stop after that, and I haven't checked that the deployed code matches the repo.

The fix is to compare against `calendar.MONDAY` using `date.today().weekday()`, or to compare `isoweekday()` to 1.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `isoweekday()` (Monday = 1) to `calendar.MONDAY` (= 0), so it is never true and the weekly close and stable reminders never send.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f