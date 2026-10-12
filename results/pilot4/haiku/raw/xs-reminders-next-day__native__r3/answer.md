The Monday reminders were broken by a weekday comparison in `_is_reminder_day`. I fixed it and added regression tests. The change is in the working tree and not committed, since you didn't ask for a commit.

**Cause:** `_is_reminder_day` compared `date.today().isoweekday()` (Monday is `1`) to `calendar.MONDAY` (which is `0`). The check could never pass, so `case_close_reminder` and `case_stable_reminder` never sent on Mondays. The scheduler logs match this: Monday 2025-08-04 sent 6 case reminders and Monday 2025-08-11 sent 5, but Monday 2025-08-18 sent none. The deploy `main-81d8ae42` (2025-08-13) contains the bad commit, and the previous deploy `main-b05613b5` does not.

**Changes:**
- `src/dispatch/case/scheduled.py`: `date.today().isoweekday()` → `date.today().weekday()`, which is 0-based like `calendar.MONDAY`. One line.
- `tests/case/test_case_scheduled.py` (new):
  - `test_is_reminder_day` checks Monday is true and Sunday/Tuesday are false.
  - `test_case_stable_reminder_only_sends_on_monday` runs the real stable-reminder body on a pinned Monday and a pinned Tuesday.
- The new tests fail on the original code (3 failures) and pass with the fix.

**Test results:** `python -m pytest` gives 365 passed, 8 failed, 4 skipped. The 8 failures are in `tests/ai`, `tests/database`, and `tests/entity`. They also fail on the original code, so they predate this change. `ruff` isn't installed here, so I didn't lint.

**Not changed:** the scheduler also logs a `None` subtraction error in `case_close_reminder` for triage cases with no `triage_at`. Those cases are skipped, and this error did not cause the missed Mondays, so I left it alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18