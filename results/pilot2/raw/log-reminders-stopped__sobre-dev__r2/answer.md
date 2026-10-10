The weekly Monday reminders stopped because of a Monday check that can never be true. It came in with a refactor on 2025-08-12.

- **Logs:** "Case close reminder sent" appears on 2025-07-28, 2025-08-04 and 2025-08-11, which are all Mondays. There are none after that, and the 08-18 Monday is missing.
- **Code:** `_is_reminder_day()` returns `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0. The comparison is therefore false every day. Both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) use this helper, so both went silent. The commit swapped the old inline check `isoweekday() == 1` for it.
- **Distractor:** The `TypeError: datetime - NoneType` errors from `case_close_reminder` and `case_stable_reminder` are present from 2025-07-28, while reminders were still being sent. They come from cases with no timestamp, and the per-case `try/except` isolates them, so they aren't the cause.
- **Fix:** Use `date.today().weekday() == calendar.MONDAY`, or compare `isoweekday()` to 1.

I didn't change any code or run any tests.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0), so the check is never true and the weekly case close and stable reminders never fire.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f