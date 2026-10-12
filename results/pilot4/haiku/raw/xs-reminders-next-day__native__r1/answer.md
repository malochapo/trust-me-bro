The weekly Monday reminders were never sent after the Aug 13 deploy. The fix is one line and the regression test is in place.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0). The check was never true, so the case close and stable reminders were skipped every day. Commit `c509d45e` (Aug 12, "refactor(case): share the weekly reminder check") moved the old `isoweekday() == 1` check into this helper and introduced the mismatch. It shipped in `main-81d8ae42`, which the scheduler started on 2025-08-13. The `main-b05613b5` image from before that was not affected. The last case close reminders went out on Monday 2025-08-11, and none went out on 2025-08-18.

**Fix:** `date.today().weekday() == calendar.MONDAY`. I did not commit it.

**Regression test:** `tests/case/test_case_scheduled.py` (new) pins the date to Monday 2025-08-18 and to Tuesday, and runs the registered case close and stable reminder tasks against a case that has been in triage or stable for 8 days. On the buggy line, 4 of the 6 tests fail. With the fix, all 6 pass. `python -m pytest tests/case` gives 21 passed, and ruff passes on both files.

**Not fixed:** `case_close_reminder` has no `triage_at is None` guard, although `case_stable_reminder` has one. Cases with no `triage_at` raise `TypeError` at `scheduled.py:47` on every daily run. The per-case `try/except` catches it, so other cases still get reminders, but those cases never do. This is a separate bug and I left it alone. Adding the same guard would fix it.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18