**Root cause:** The weekly Monday check compares Python's `isoweekday()` (Monday = 1) against `calendar.MONDAY`, which is 0. The condition is never true, so the long-running triage and stable close reminders are never sent.

**How it was introduced:** Commit `c509d45e` ("refactor(case): share the weekly reminder check", Aug 12) moved the inline `date.today().isoweekday() == 1` into a helper, `_is_reminder_day()`, and wrote the constant as `calendar.MONDAY`. Before that commit, both jobs compared against the literal `1`, which is correct.

**Evidence:**
- `calendar.MONDAY == 0`, and `date(2025, 8, 11).isoweekday() == 1` (I checked both with `python3 -I`).
- Before the refactor, Monday runs logged "Case close reminder sent" lines, e.g. 2025-08-04 (`api.log`/`scheduler.log`). On Monday 2025-08-18 the scheduler logged only triage reminders, and no close or stable reminders.
- The daily triage reminders are unaffected because they don't use `_is_reminder_day()`, which matches the symptom.

**Separate issue, not the cause:** `case_close_reminder` logs `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` at `scheduled.py:47` for triage cases with no `triage_at`. The per-case `try/except` catches it, so it skips only those cases. It doesn't explain the missing Monday reminders, but it's worth fixing with the same guard that `case_stable_reminder` already has. I haven't changed any code.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
CAUSE: It compares `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (Monday = 0), so the weekly Monday gate is never true and the close and stable reminders are never sent.
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f