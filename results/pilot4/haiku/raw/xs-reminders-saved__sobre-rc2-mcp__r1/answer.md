Fixed the weekday bug, added a regression test, and the test suite for `tests/case` passes (19 passed). The change is uncommitted in the working tree.

**What was wrong:** Commit `c509d45e` replaced `date.today().isoweekday() == 1` with a shared helper, `_is_reminder_day()`, that compared `isoweekday()` against `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the check was never true. Both `case_close_reminder` and `case_stable_reminder` depend on it, so the weekly reminders stopped. Triage reminders are not affected.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based, so Monday matches.

**Regression test:** `tests/case/test_case_scheduled.py` patches `date` and checks `_is_reminder_day()` on a Monday, Sunday, Tuesday, and Friday. I ran it before the fix and the Monday case failed, which confirms it catches the bug.

**Evidence from the logs:** Monday 2025-08-11 still sent close and stable reminders on the old image. On Monday 2025-08-18 the scheduler ran both jobs with no sends. The `main-81d8ae42` image had been running since 2025-08-13.

**Not done:**
- I did not commit, since you didn't ask for one.
- I did not run the full test suite, only `tests/case`.
- `case_close_reminder` also logs a `NoneType` error on `case.triage_at` every day, including 2025-08-18. Those cases are skipped. This is a separate problem and I did not change it.
- I updated the memory note to reflect that the fix is applied.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18