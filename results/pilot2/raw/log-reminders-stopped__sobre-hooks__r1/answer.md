The weekly check that the refactor commit `c509d45e` introduced can never be true, so the Monday reminders stopped.

The refactor moved the old inline test `date.today().isoweekday() == 1` into a new helper, `_is_reminder_day()`. The helper compares against `calendar.MONDAY`, which is `0`. `isoweekday()` numbers Monday as `1`, and its range is 1–7, so it never returns `0`. As a result, `case_close_reminder` (triage cases) and `case_stable_reminder` (stable cases) never send their weekly reminders.

The daily triage reminders come from `case_triage_reminder`. It doesn't use `_is_reminder_day()`, so it kept working. That matches what assignees are seeing.

The refactor landed on 2025-08-12. The scheduler log's 07-28 to 08-01 entries still show "Case close reminder sent" lines, so the Monday reminders worked on the old code. I didn't read the log past 08-01 or confirm that no such lines appear after 08-12.

The log also shows `NoneType` subtraction errors in `case_close_reminder` and `case_stable_reminder`, from cases with no `triage_at` or `stable_at`. That is a separate, older problem. Commit `32fa810f` already guards the `stable_at` case, and the log's line numbers suggest those errors came from the older, unguarded code. The `triage_at` subtraction in `case_close_reminder` is still unguarded in the current repo.

To fix it, change the helper to `date.today().isoweekday() == 1`, or use `date.today().weekday() == calendar.MONDAY`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday is 1) to `calendar.MONDAY` (which is 0), so the check is never true and the weekly close and stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f