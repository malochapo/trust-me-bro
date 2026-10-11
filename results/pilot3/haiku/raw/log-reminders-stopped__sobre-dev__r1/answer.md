The root cause is a constant mismatch in the new `_is_reminder_day()` helper. It compares `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0), so it is never true and the Monday gate never opens.

**Evidence**
- `calendar.MONDAY` is `0` in Python. `isoweekday()` returns `1` for Monday. The check `date.today().isoweekday() == calendar.MONDAY` is therefore always False.
- Commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) replaced the inline `date.today().isoweekday() == 1` with this helper. The inline version was correct.
- The logs match. Case close/stable reminders were sent on 2025-07-28, 08-04, and 08-11 (Mondays). Nothing was sent for case reminders on 08-18 or later. The one 08-18 "close reminder" line is an incident reminder, not a case reminder.
- `case_triage_reminder` does not use the helper, so the daily triage reminders keep arriving.

**Fix:** compare against `1`, or use `calendar.MONDAY + 1`, or better, compare `date.today().weekday() == calendar.MONDAY`, since `weekday()` is the zero-based form that matches `calendar.MONDAY`.

**Side note (not the cause):** the scheduler log shows `case_close_reminder` raising `datetime - NoneType` at line 47 every day, from `case.triage_at` being `None`. It is caught by the per-case `try/except`, so it does not stop other cases, but `case_close_reminder` lacks the `stable_at`-style guard that `case_stable_reminder` got in `32fa810f`. That is worth a separate fix.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: The helper compares `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0), so the Monday check is always False and both long-running case reminders are suppressed.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f