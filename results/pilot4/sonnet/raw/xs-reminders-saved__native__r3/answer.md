Fixed `_is_reminder_day()` in `src/dispatch/case/scheduled.py` and added a regression test. I haven't committed either change.

**Cause:** commit `c509d45e` added `_is_reminder_day()` as `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` returns 1 for Monday but `calendar.MONDAY` is 0, so the check never passed. `case_close_reminder` (triage) and `case_stable_reminder` both depend on it, so both stopped sending.

**Fix:** it now uses `date.today().weekday() == calendar.MONDAY`.

**Test:** `tests/case/test_case_scheduled.py` mocks today's date and checks a Monday, a Tuesday and a Sunday. It passes with the fix. With the fix stashed, the Monday case fails, so it would have caught the bug.

**Evidence in the logs:**
- "Case close reminder sent" appears on 2025-07-28, 08-04 and 08-11, and not on 08-18.
- Commit `c509d45e` is an ancestor of `81d8ae42`, the commit the `main-81d8ae42` image is built from.
- That image rolled out on 2025-08-13 at about 16:40Z, so 08-18 was the first Monday after it.
- I only ran the new test file, not the full suite.

Cases that were missed only get reminded on the first Monday after this fix is deployed.

`case_close_reminder` also logs a `datetime - None` error for cases with no `triage_at`. That predates the regression and I left it alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18