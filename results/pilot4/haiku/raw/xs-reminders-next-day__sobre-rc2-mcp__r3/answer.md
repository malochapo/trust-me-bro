The Monday reminders were broken by a one-line weekday mismatch, and I've fixed it. The fix is in the working tree and not committed.

**Cause:** `_is_reminder_day()` in `src/dispatch/case/scheduled.py` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0). The check was never true, so the close and stable reminders were silently skipped every week. The bad line came in with `c509d45e` on Aug 12, 2025. It was refactored out of the previous `isoweekday() == 1` check, which was correct.

**Evidence from the logs:**
- Image `main-b05613b5` was running through Aug 13 and still had the correct check. Reminders were sent on Monday Aug 11 (for example, "Case close reminder sent to …" at 18:00).
- Image `main-81d8ae42` (which contains `c509d45e`) started on Aug 13.
- On Monday Aug 18, both reminder jobs ran at 18:00 and sent nothing. The same is true for Aug 25 and Sep 1.

**Fix:** `date.today().weekday() == calendar.MONDAY`, which compares like with like.

**Regression test:** `tests/case/test_case_scheduled.py` freezes "today" to each day of one week and asserts `_is_reminder_day()` is true only on Monday. Against the old code it fails on Monday and passes on the other six days. With the fix, `python -m pytest tests/case` gives 22 passed.

I didn't commit. Note that the Aug 18 run also logged a per-case error in `case_close_reminder` (`datetime - NoneType` on `triage_at`). It's caught per case, so it doesn't block other cases, but cases with no `triage_at` will never get a reminder. I left that alone since it's a separate issue.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18