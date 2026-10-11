The cause is a refactor that changed the Monday check from `1` to `calendar.MONDAY`, which is `0`.

- **Before:** `date.today().isoweekday() == 1`. `isoweekday()` returns 1 for Monday, so this worked.
- **Commit `c509d45e`, 2025-08-12:** "share the weekly reminder check" moved that test into `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. It now reads `date.today().isoweekday() == calendar.MONDAY`.
- **Why it breaks:** `calendar.MONDAY` is 0, and `isoweekday()` never returns 0. The check is always false, so `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) never send anything.
- **Why the daily triage reminders still arrive:** `case_triage_reminder` doesn't use this check.

I haven't run the code or confirmed the fix. The fix is to compare against `isoweekday() == 1` or use `date.today().weekday() == calendar.MONDAY`.

The `TypeError: ... 'NoneType'` errors in `scheduler.log` are a separate problem. They come from cases with no `stable_at` or `triage_at` date, and they appear in the logs from 2025-07-28, before the regression. They are not what stopped the Monday reminders. `case_stable_reminder` now skips cases without `stable_at` (commit `32fa810f`), but `case_close_reminder` still subtracts `case.triage_at` unguarded.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (= 0), so the check is never true and the weekly close and stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f