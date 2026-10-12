The weekly Monday reminders are fixed. The bug was a weekday numbering mismatch. I left the change uncommitted.

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, but `calendar.MONDAY` is 0, so the check was never true. Both the triage and stable reminders depend on this check, so neither sent on Mondays after the deploy.

**Fix** (`src/dispatch/case/scheduled.py`): changed the comparison to `date.today().weekday()`, which uses the same 0-based numbering as `calendar.MONDAY`.

**Regression test** (`tests/case/test_case_scheduled.py`, new): pins `date.today()` in the module and checks that `_is_reminder_day()` is true on Monday 2025-08-18 and false Tuesday through Sunday. With the bug restored, the Monday test fails; with the fix, both pass. `python -m pytest tests/case` passes (17 tests).

**Timeline from the logs:** the scheduler started on image `main-81d8ae42` on 2025-08-13 at 16:40 UTC, and that image includes commit `c509d45e`. The Monday 2025-08-11 run used the old image, so it was the last Monday that could have sent. The case reminder job ran on Monday 2025-08-18 at 18:00 with no send, so that is the first missed Monday. The logs don't record individual sends, so I confirmed the missed run from the job timing and the code, not from a send count.

**Separate issue, not fixed:** the scheduler logs show `case_close_reminder` failing daily with `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` on `case.triage_at`. The per-case `try/except` catches it, so it doesn't block other cases, but triage cases with no `triage_at` are skipped every day. That needs its own look.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18