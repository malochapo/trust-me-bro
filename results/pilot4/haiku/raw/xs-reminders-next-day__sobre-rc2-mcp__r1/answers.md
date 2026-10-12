**Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", Jordan Lee, 2025-08-12) moved the Monday check into a helper that compares against the wrong constant. The helper is in `src/dispatch/case/scheduled.py:31-33`:

```python
def _is_reminder_day() -> bool:
    return date.today().isoweekday() == calendar.MONDAY
```

`isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0 (Python's calendar counts Monday as 0). I confirmed both values with Python. The old code compared `isoweekday()` to `1`, which was correct. The refactor replaced that with `calendar.MONDAY`, so `_is_reminder_day()` is never true. Since the helper gates both `case_close_reminder` (triage) and `case_stable_reminder` (stable), the weekly reminders stop for both. The daily triage reminders (`case_triage_reminder`) don't use this helper, so they keep working.

**Deploy that shipped it:** `main-81d8ae42`, started on the scheduler and web pods at 2025-08-13 16:40 UTC (`scheduler.log:18851`, `api.log:13201`). `c509d45e` is an ancestor of that commit. The previous image, `main-b05613b5`, started 2025-07-30 and was still correct.

**Log evidence:**
- Monday 2025-08-11 (before the deploy): `Case close reminder sent` appears for several assignees (`scheduler.log:16799-16808`).
- Monday 2025-08-18 (after the deploy): zero `Case close reminder sent` lines since 08-13.
- Triage reminders still send after the deploy, which matches the report.

**Things I noticed but did not verify or act on:**
- `case_stable_reminder` and `case_close_reminder` log a `NoneType` error on every daily run from 07-28 (`stable_at` and `triage_at` are null on some cases). These are caught per case, so they don't block the other cases, but they pollute the logs and are a separate issue. The commit `32fa810f` ("not all cases have a stable_at date") in the same window looks like an attempt at the `stable_at` part; it's in `81d8ae42` too, so the stable error should be gone after 08-12, but the `triage_at` error in `case_close_reminder` is still there.
- `api.log` has no reminder-related entries; I used it only for the deploy markers.

No code has been changed. When you want the fix, the change is to make the helper compare against the same numbering as `isoweekday()` (for example `== 1`, or `calendar.MONDAY + 1`), and add a test that pins Monday to the reminder day.

----- next turn -----

The weekly reminders were dropped because the Monday check compared the wrong numbering. I've fixed it and added a regression test.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The comparison was never true, so `case_close_reminder` and `case_stable_reminder` skipped every day. The bug came in with `c509d45e` on 2025-08-12, which refactored the check into this helper. The scheduler logs show reminders on Mondays 2025-08-04 and 2025-08-11, then none after that. The first missed Monday was 2025-08-18, and the logs run through 2025-08-20 with no close reminders sent that day. The scheduler started the image `main-81d8ae42` on 2025-08-13, and that image contains `c509d45e`.

**Changes:**
- `src/dispatch/case/scheduled.py`: `isoweekday()` is now `weekday()`, which uses the same 0-based numbering as `calendar.MONDAY`.
- `tests/case/test_case_scheduled.py` (new): checks that only Monday returns true across a full week, and that Monday 2025-08-18 is a reminder day. Against the old code, the Monday cases fail, and with the fix all 8 pass. `python -m pytest tests/case` passes (23 tests).

The change is not committed.

**Not fixed, but noticed:** the scheduler log has `unsupported operand type(s) for -: 'datetime.datetime' and 'NoneType'` errors on `case.triage_at` in `case_close_reminder`, every day from 2025-07-28 onward. The per-case `try` catches them, so those cases are skipped silently. This predates the weekday bug and needs a separate fix.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18