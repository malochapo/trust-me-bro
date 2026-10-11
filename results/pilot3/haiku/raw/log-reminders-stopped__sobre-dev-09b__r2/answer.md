The root cause is in the `_is_reminder_day()` helper, which a refactor on 2025-08-12 introduced. It compares ISO weekday numbers (Monday = 1) against `calendar.MONDAY`, which is 0, so the check is never true and the weekly Monday reminders never fire.

**Evidence**
- The commit `c509d45e` (Aug 12, "refactor(case): share the weekly reminder check") replaced `date.today().isoweekday() == 1` with `_is_reminder_day()`, which uses `date.today().isoweekday() == calendar.MONDAY`.
- `calendar.MONDAY` is 0 in Python, so the helper always returns False.
- The logs match. On Monday 2025-08-11, which was before the refactor landed, the scheduler sent 6 "Case close reminder sent" lines. On Monday 2025-08-18 it sent none; only incident close reminders appear that day. Daily triage reminders kept firing throughout, because `case_triage_reminder` doesn't use this check.
- The `TypeError` on `case.stable_at` in the logs is a separate, earlier problem. It was already guarded in the current code by `32fa810f` and did not cause the mid-August change.

I haven't changed any code. A fix would be `date.today().weekday() == calendar.MONDAY` (`weekday()` is 0-based like `calendar.MONDAY`), or keep `isoweekday() == 1`. A regression test that pins the helper to a Monday date would catch this.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the weekly Monday check is never true and the long-running triage and stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f