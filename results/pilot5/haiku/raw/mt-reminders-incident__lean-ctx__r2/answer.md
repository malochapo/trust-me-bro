**Recap**

- **Missing weekly reminders:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so the check never passed. Weekly case close and stable reminders stopped. Daily triage reminders were unaffected. The bug came in with `c509d45e` on 2025-08-12 and reached production in the `main-81d8ae42` deploy, which started on the scheduler and web pods on 2025-08-13 at 16:40Z. The Monday 2025-08-11 run sent 5 case close reminders; Monday 2025-08-18 sent none.
- **Fix:** `date.today().weekday() == calendar.MONDAY`. A parametrized test covers Monday through Sunday; it fails on the old line and passes with the fix.
- **Evening TypeError:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Slack handlers set `status = triage` directly, bypassing `case_triage_status_flow`, so those cases have no `triage_at`. The job now uses `case.triage_at or case.created_at`. Three tests cover the fallback, the recent-case skip, and `triage_at` precedence; the fallback test fails on the old line.
- **Tests:** `tests/case` passes (22). The full suite has 369 passed and 4 skipped, plus 8 failures in `ai`, `database`, and `entity` that also fail without these changes.
- **Not done:** Nothing is committed. The Slack handlers still skip `triage_at`, and `case_stable_reminder` still skips cases without `stable_at`. Both are outside what you asked for.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at