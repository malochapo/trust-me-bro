The root cause is a weekday mismatch in the helper that c509d45e introduced. `calendar.MONDAY` is `0`, but `isoweekday()` returns `1` for Monday, so the Monday check never passes.

**Evidence**
- `calendar.MONDAY == 0` in this Python 3.11 runtime. `date.today().isoweekday()` returns 1 on Mondays (ISO numbering is 1–7), so `_is_reminder_day()` is always False.
- The close-reminder logs match. "Case close reminder sent" appears 6 times on Monday 2025-08-11, the last Monday before the change, and 0 times on Monday 2025-08-18. The one close-reminder line on 08-18 is for an incident, not a case.
- The triage reminder (`case_triage_reminder`) has no weekday check, so it keeps firing daily, as reported.
- The original code compared `date.today().isoweekday() == 1`. Commit c509d45e (Aug 12, "refactor(case): share the weekly reminder check") moved that check into `_is_reminder_day()` and changed the constant from `1` to `calendar.MONDAY`. That is the first Monday-less day after the change, and it matches the "since mid-August" timing.
- The stable-case reminder errors in the logs (`case.stable_at` is None) are a separate, earlier problem already fixed in 32fa810f. They are not the cause of the missing reminders.

**Fix (not applied; you asked for the root cause only)**
Use `date.today().weekday() == calendar.MONDAY`, which keeps the `calendar` constant and matches its 0-based numbering. Alternatively, compare `isoweekday()` against `1`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (ISO Monday = 1) against `calendar.MONDAY` (Python Monday = 0), so the weekly Monday check never passes.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f