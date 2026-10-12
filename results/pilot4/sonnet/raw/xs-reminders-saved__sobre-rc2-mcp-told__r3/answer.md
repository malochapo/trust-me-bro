Weekly reminders will go out on Mondays again. The new tests pass with the fix and fail without it. I ran only the new test file, not the full suite.

**Cause:** `_is_reminder_day()` compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` numbers Monday as 1, while `calendar.MONDAY` is 0. The check therefore matched Tuesdays, not Mondays. The scheduler runs the reminders daily at 18:00, so they went out on Tuesdays instead.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday()`, which numbers Monday as 0 like `calendar.MONDAY`.

**Regression test:** `tests/case/test_case_scheduled.py`.
- It checks `_is_reminder_day()` on a Monday, Tuesday and Sunday.
- It runs the close and stable reminder tasks on a case older than a week. It expects a send on Monday and none on Tuesday.

**Evidence from the logs:**
- Reminders were sent on 2025-07-28, 2025-08-04 and 2025-08-11.
- Commit `c509d45e` ("share the weekly reminder check", 2025-08-12) introduced the bug.
- The scheduler was redeployed on 2025-08-13 as `main-81d8ae42`, which contains that commit.
- The first Monday after the deploy is 2025-08-18.
- I did not look for sends after 2025-08-13 in `scheduler.log`. The 2025-08-18 date comes from that Monday following the deploy.

**Separate problem (not changed):** the logs also show `unsupported operand type(s) for -: 'datetime' and 'NoneType'` errors in `case_close_reminder` and `case_stable_reminder`. This looks like cases with no `triage_at` or `stable_at` timestamp. The `try/except` in each reminder loop catches it, so it doesn't block the other cases.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18