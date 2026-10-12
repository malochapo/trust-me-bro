The weekly Monday reminders stopped because `_is_reminder_day()` compared `isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). It never matched, so the Monday check was always false.

- **Cause:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the check into `_is_reminder_day()`. The original code compared against the literal `1`, which was correct.
- **Shipped:** deployed as `main-81d8ae42` on 2025-08-13 16:40 UTC, on both the scheduler and the web containers. The scheduler was on `main-b05613b5` before that, which doesn't include the refactor.
- **Evidence:** case close reminders went out on Mondays 2025-07-28, 08-04 and 08-11. On 2025-08-18 both `case_close_reminder` and `case_stable_reminder` ran at 18:00 and sent nothing.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. `weekday()` and `calendar.MONDAY` use the same 0-based numbering.

**Regression test:** `tests/case/test_case_scheduled.py` freezes "today" to a Monday, a Tuesday and a Sunday, and checks `_is_reminder_day()` for each. With the old code the Monday case fails. With the fix all three pass, and `python -m pytest tests/case` passes (18 tests).

Not done:
- I didn't commit or deploy anything.
- The logs end on 2025-08-20, so I can't confirm the state of later Mondays. The bug would have skipped them too.
- Unrelated, not fixed: every day the scheduler logs an `unsupported operand type(s) ... NoneType` error for cases with no `triage_at` or `stable_at`. The per-case `try` catches it, so it doesn't stop the other reminders, but it adds noise every run.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18