**Root cause:** `_is_reminder_day()` compares `date.today().isoweekday()` with `calendar.MONDAY`. Those use different numbering. `isoweekday()` is 1 for Monday, but `calendar.MONDAY` is 0, so the check is always False and the weekly close and stable reminders never send. The daily triage reminder doesn't call this helper, so it keeps going.

**Evidence:**
- `python3 -c "import calendar; print(calendar.MONDAY)"` prints `0`. `datetime.date(2025, 8, 18).isoweekday()` is `1`.
- `c509d45e` (Aug 12, "refactor(case): share the weekly reminder check") replaced the inline `date.today().isoweekday() == 1` with `_is_reminder_day()`. The inline version was correct; the refactor introduced the mismatch.
- `scheduler.log` shows "Case close reminder sent" on Monday 2025-08-04 (6 sends) and Monday 2025-08-11 (5 sends), which is before the refactor. There are none on 2025-08-18, the first Monday after it.
- "Case triage reminder sent" continues daily through 2025-08-18, 08-19 and 08-20, matching the report.

**Fix:** Use `date.today().weekday() == calendar.MONDAY` (0-based), or compare `isoweekday() == 1` as the old code did. I haven't changed the code. A separate issue also appears in the logs: `case_close_reminder` raises a `None` subtraction on `case.triage_at` (e.g. 2025-08-20 line 55). It's unrelated to the missing Monday reminders, but it's worth fixing with the same guard that `case_stable_reminder` got in `32fa810f`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0), so the weekly Monday gate is never true and the weekly close and stable reminders never send.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f