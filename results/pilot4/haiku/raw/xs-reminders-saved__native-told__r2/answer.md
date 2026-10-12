The Monday reminder bug is fixed and covered by a regression test. The fix is in the working tree and not committed.

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the check was never true. Commit c509d45e introduced it when it moved the check into a shared helper. The image `main-81d8ae42` shipped it on 2025-08-13 at 16:40Z.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`, which matches the constant the code already uses.

**Regression test:** `tests/case/test_case_scheduled.py` pins `date.today()` to each day of one week and asserts that only Monday passes. It fails on the old code on Monday and passes after the fix. `python -m pytest tests/case` passes (22 tests). I did not run the full suite.

**Logs:** Close reminders went out on Mondays 2025-08-04 and 2025-08-11. On 2025-08-18 only triage reminders went out, so that is the first missed Monday.

**Not done:** The 2025-08-18 scheduler log also shows a `TypeError` in `case_close_reminder`, because some triage cases have no `triage_at` and the subtraction runs before the weekday gate. It is caught per case, so it does not block other sends, but it repeats daily. I left it alone because it's a separate change; adding a `triage_at is None` guard, as `case_stable_reminder` already has for `stable_at`, would fix it.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18