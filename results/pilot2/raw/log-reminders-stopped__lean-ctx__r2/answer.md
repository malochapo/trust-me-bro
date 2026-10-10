Root cause: `_is_reminder_day()` compares `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, because the `calendar` module numbers weekdays from Monday = 0. The comparison is therefore true only on Sundays (isoweekday 7 ≠ 0, so effectively never). The scheduler runs the jobs at 18:00 UTC, so the Monday-only check never passes and `send_case_close_reminder` is never called.

How this fits the logs:
- The last "Case close reminder sent" entries in the logs are on Monday 2025-08-11 (5 sends). On Monday 2025-08-18 there are none.
- Commit c509d45e landed on 2025-08-12, which refactored the inline `date.today().isoweekday() == 1` check into the shared helper.
- The deployed line numbers in the tracebacks shift on 2025-08-13 (line 43 → 47), which matches the new code going live.
- The daily triage reminders don't use this check, so they kept working.

The `triage_at`/`stable_at` None TypeErrors in the logs are a separate, pre-existing issue. They are caught per case, so they don't block other cases.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (= 0), so the Monday-only check never passes and no weekly case close/stable reminders are sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f