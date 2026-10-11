The weekly Monday reminders stopped because a refactor swapped a literal `1` for `calendar.MONDAY`, which is `0`. The new check can never match.

- **The bug:** commit c509d45e (Aug 12, "share the weekly reminder check") added `_is_reminder_day()`. It returns `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0 (I confirmed this in Python, and 2025-08-18 gives `isoweekday()` of 1). So the check is true only if `isoweekday()` returns 0, which it never does.
- **What it affects:** `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) both gate on `_is_reminder_day()`, so neither sends anything now.
- **Why the daily reminders still arrive:** `case_triage_reminder` doesn't use this check.
- **Evidence in the logs:**
  - On Monday 2025-08-11, before the deploy, the scheduler logged six "Case close reminder sent to …" lines.
  - On Monday 2025-08-18, after the deploy, it logged none. The pod changed between those two Mondays, and the traceback line numbers moved from line 43 to line 47, which matches the added helper.
- **Unrelated noise:** the `TypeError` from a case with a null `triage_at` or `stable_at` has been logged on every run since 2025-07-28. It is caught per case, so it doesn't stop the other reminders. It is not the cause.

The fix is to compare against `calendar.MONDAY + 1`, or use `date.today().weekday() == calendar.MONDAY`. I haven't changed any code.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (= 0), so the check is never true and the Monday close and stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f