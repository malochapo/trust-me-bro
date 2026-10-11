The weekly Monday reminders stopped because a refactor changed the Monday check so that it can never be true.

- **Cause:** commit `c509d45e` (Aug 12) replaced `date.today().isoweekday() == 1` with a shared helper, `_is_reminder_day()`. The helper compares `isoweekday()` against `calendar.MONDAY`. `isoweekday()` numbers Monday as 1 and runs 1–7. `calendar.MONDAY` is 0, because the `calendar` module numbers days 0–6. The helper therefore never returns True, and both `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) skip every send.
- **Why only the weekly reminders:** the daily triage reminder doesn't use this check, so it kept working.
- **Log evidence:** "Case close reminder sent" appears on 2025-07-28, 08-04 and 08-11 (4, 6 and 5 sends). It does not appear on Monday 08-18 or any later day in the logs. The refactor was committed on 08-12, which matches the mid-August start.
- **Unrelated errors:** the `datetime - NoneType` errors in the same functions appear from 07-28 onward, so they predate the refactor and don't explain the stop.
- **Fix:** compare against `calendar.MONDAY + 1`, or use `date.today().weekday() == calendar.MONDAY`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (= 0), so the check is never true and the weekly close and stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f