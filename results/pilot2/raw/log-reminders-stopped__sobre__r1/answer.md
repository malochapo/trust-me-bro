Root cause found: `calendar.MONDAY` is 0, but `isoweekday()` returns 1 for Monday.

The weekly Monday check for long-running cases lives in the helper `_is_reminder_day`, which compares `date.today().isoweekday()` with `calendar.MONDAY`. Before commit `c509d45e` (12 Aug, "share the weekly reminder check"), both `case_close_reminder` and `case_stable_reminder` tested `isoweekday() == 1`.

The two numbering schemes differ:
- `isoweekday()` numbers Monday as 1 and Sunday as 7. It never returns 0.
- `calendar.MONDAY` is 0, because the `calendar` module counts weekdays from Monday = 0.

So `_is_reminder_day()` can never be true, and both reminders are silently skipped on every day, Mondays included.

The logs match this:
- **Last reminders sent:** Mondays 28 Jul, 4 Aug and 11 Aug have "Case close reminder sent" lines. After the 12 Aug commit, 18 Aug has none.
- **Daily triage reminders:** they use a different function that doesn't call the helper, so they keep arriving.
- **Tracebacks:** the `NoneType` tracebacks are a separate issue. They are caught per case and don't stop the loop. The stable-case ones were fixed in `32fa810f` and stopped on 13 Aug. They are not the cause here, though the triage one still logs one error a day.

I haven't changed any code. The fix is to compare against `calendar.MONDAY` using `date.today().weekday()`, or to compare `isoweekday()` with 1.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (= 0), so it never returns true and the weekly case close and stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f