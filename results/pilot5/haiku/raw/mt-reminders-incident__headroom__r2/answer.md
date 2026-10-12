## Recap

- **Weekly reminders stopped:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The check was never true. Commit `c509d45e` introduced it as part of a refactor, and it shipped in image `main-81d8ae42` on 2025-08-13. Monday 2025-08-11 still sent 5 reminders, which was before the deploy. Monday 2025-08-18 sent none.
- **Fix:** the helper now uses `date.today().weekday()`, which matches `calendar.MONDAY`. Test: `test_is_reminder_day` in `tests/case/test_case_scheduled.py`. It fails on the old line.
- **Evening TypeError:** `case_close_reminder` subtracted `case.triage_at` from `utcnow()`. Some triage cases have `triage_at` set to NULL, so the subtraction raised `datetime - NoneType`. The per-case `try/except` logged it and skipped the case. The triage flow sets `triage_at` only on status transitions, so cases that reached triage another way never get it. I inferred this from the code and didn't check the database.
- **Fix:** the job counts from `case.triage_at or case.created_at`. Tests: three cases in `tests/case/test_case_scheduled.py`. One checks a case with no `triage_at` created eight days ago, which is now reminded. One checks a recent case with no `triage_at`, which is not. One checks that `triage_at` still wins when set. The new reminder test fails without the fallback.
- **Test status:** `python -m pytest tests/case` passes (21 tests). I couldn't run `ruff`, since it isn't installed here.
- **Not committed:** the changes are in the working tree (`src/dispatch/case/scheduled.py` and the new test file).

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```