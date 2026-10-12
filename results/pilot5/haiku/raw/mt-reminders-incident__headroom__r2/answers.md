## Root cause

`calendar.MONDAY` is `0`, not `1`. Python's `calendar` module numbers Monday as 0, while `date.isoweekday()` numbers Monday as 1. The refactor in `c509d45e` replaced the working check with `_is_reminder_day()`, which compares the two:

```python
# src/dispatch/case/scheduled.py:31-33 (HEAD)
def _is_reminder_day() -> bool:
    """Reminders about long-running cases go out once a week, on Mondays."""
    return date.today().isoweekday() == calendar.MONDAY   # 1 == 0 -> always False
```

The code it replaced was `date.today().isoweekday() == 1`, which was correct. So `_is_reminder_day()` is always False, and the gate `if q >= 1 and _is_reminder_day()` in both `case_close_reminder` (triage) and `case_stable_reminder` (stable) never passes. The weekly reminders for both kinds of case stop.

The daily triage reminder is `case_triage_reminder`, which doesn't use this helper, so it keeps working. That matches what you saw.

I verified the constant directly: `calendar.MONDAY = 0`, and `date(2025, 8, 4).isoweekday() = 1`.

## The deploy

- The refactor commit is `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12).
- It shipped in production as image `registry.example.com/dispatch:main-81d8ae42`. The scheduler pod started on that image at 2025-08-13T16:40:06Z (`scheduler-mhtsgqwwx-q5q2n`, per `scheduler.log`). `c509d45e` is an ancestor of `81d8ae42` (the `fix(case): exclude resolved_by in update (#6183)` commit).

## Log evidence

- **Monday 2025-08-04** (before the deploy): 5 `Case close reminder sent` lines for triage and stable cases.
- **Monday 2025-08-11** (before the deploy, image `main-b05613b5`): 5 sent.
- **Monday 2025-08-18** (after the deploy): 0 sent.

## Side issues (not the cause)

- `case_close_reminder` and `case_stable_reminder` log a `datetime - NoneType` error on most days. The stable path is guarded by `if case.stable_at:` from `32fa810f`, but the `case_close_reminder` path still reads `case.triage_at` without a guard. Those errors are caught per case, so they don't stop the other cases, but they add noise to the scheduler logs. Worth a separate look.

I haven't changed any code, as you asked. The fix would be to compare against `1` or use `calendar.MONDAY` with `date.today().weekday()`, which is 0-based. Tell me if you want me to make that change.

----- next turn -----

The weekly reminders are fixed, and a regression test covers the bug. I haven't committed anything.

**The fix** (`src/dispatch/case/scheduled.py:33`): `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Both sides are 0-based (Monday is 0), so the helper and the constant agree. The previous line compared the 1-based `isoweekday()` against `calendar.MONDAY` (0), so it was never true.

**The regression test** (`tests/case/test_case_scheduled.py`): it patches the module's `date` to a Monday, a Tuesday, and a Sunday, and asserts `_is_reminder_day()` returns True only on Monday. I didn't add a time-freezing library, since none is installed. I confirmed the Monday case fails when the old `isoweekday()` line is put back, and passes with the fix.

**Test results** with `python -m pytest`:
- `tests/case/test_case_scheduled.py`: 3 passed.
- `tests/case/`: 18 passed.

I couldn't lint or format-check the changed files because `ruff` isn't installed in this environment.

The test checks the weekday helper, not the full scheduled job. It doesn't exercise `case_stable_reminder` or `case_close_reminder` end to end, so the gating in those functions is covered only by the helper's result.

----- next turn -----

The close reminder now counts from `created_at` when `triage_at` is missing, and the tests cover it. Nothing is committed.

**What causes the TypeError:** `case_close_reminder` computes `datetime.utcnow() - case.triage_at`. Some triage cases have `triage_at` set to NULL. The `TypeError` is `datetime - NoneType`, and the per-case `try/except` logs it and moves on. That's why only the job's own error line appears each evening, and why those cases never get a reminder.

I inferred the NULL from the code, not the data. `triage_at` is set only by `case_triage_status_flow`, which runs on status transitions, so a case that reached triage another way never gets a value. I couldn't query the production database to confirm.

**The fix** (`src/dispatch/case/scheduled.py`):
```python
# cases that never recorded a triage time count from when they were created
triage_start = case.triage_at or case.created_at
span = datetime.utcnow() - triage_start
```

**Tests** (`tests/case/test_case_scheduled.py`), run through the registered job with the session stubbed in:
- A Monday, a triage case with no `triage_at` and created 8 days ago: a reminder is sent.
- A Monday, a triage case with no `triage_at` and created 2 days ago: no reminder.
- A Monday, a case with `triage_at` set 2 days ago but created 30 days ago: no reminder, so `triage_at` still takes priority.

With the fallback removed, the first test fails. With the fix, all 21 tests in `tests/case` pass under `python -m pytest`.

Ruff isn't installed here, so I couldn't run the linter. I kept lines within the project's 100-character limit by hand.

----- next turn -----

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