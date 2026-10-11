**Root cause:** the weekly Monday reminders stopped because of a Monday off-by-one in a refactor. The logs match this. "Case close reminder sent" appears on 2025-07-28, 08-04 and 08-11, which are all Mondays. It never appears on 08-18 or after. The daily triage reminder uses a different code path, so it was unaffected.

The refactor commit c509d45e (Aug 12) replaced the inline check `date.today().isoweekday() == 1` with a shared helper, `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. The helper compares `isoweekday()` to `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the helper never returns true. `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) both gate on it, so neither sends anything now. Neither reports an error, so nothing in the logs flags it.

The `TypeError ... NoneType` tracebacks in the scheduler log are unrelated. They are logged for individual cases whose `triage_at` or `stable_at` is None, they appear from 2025-07-28 onward, and the per-case `try/except` catches them.

The fix is to compare against 1, or use `date.today().weekday() == calendar.MONDAY`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it is never true and the weekly case close and stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f