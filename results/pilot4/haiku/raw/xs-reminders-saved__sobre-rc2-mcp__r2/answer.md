The weekly Monday reminders are fixed, and a regression test covers the bug.

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The comparison was never true, so `case_close_reminder` and `case_stable_reminder` never sent. The daily triage reminder doesn't use this helper, which is why it kept working.

**Logs confirm this:**
- Monday 2025-08-11 sent close reminders.
- Monday 2025-08-18 sent none, while `case_stable_reminder` and the daily triage reminder kept running.
- The 2025-08-13 image `main-81d8ae42` is the first to include the bug. The previous image `main-b05613b5` (2025-07-30) does not.

**Changes:**
- `src/dispatch/case/scheduled.py`: `date.today().isoweekday()` → `date.today().weekday()`.
- `tests/case/test_case_scheduled.py` (new): parametrized test of `_is_reminder_day()` with two known Mondays and three non-Monday days. With the old code, both Monday cases fail. With the fix, all five pass.
- I updated the memory note, which still said the fix was unapplied.

**Tests:** `python -m pytest tests/case` passes (20 tests). I did not run the full suite.

**Not fixed:** `case_close_reminder` logs a `'datetime' - 'NoneType'` error on every run at `scheduled.py:47`, because `triage_at` can be None. Those cases are skipped. Fixing it would be a separate change.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18