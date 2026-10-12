## Recap

**Weekly Monday reminders stopped (weekday bug)**
- **Cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the Monday check into `_is_reminder_day()`. That helper compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true. The close and stable reminders were skipped every Monday. Daily triage reminders have no weekday check and kept going.
- **Deploy:** the logs show `registry.example.com/dispatch:main-81d8ae42` starting on both the scheduler and web pods at 2025-08-13 16:40Z. That commit contains `c509d45e`. The previous image, `main-b05613b5`, does not.
- **Evidence:** Monday 2025-08-11 sent 5 close/stable reminders. Monday 2025-08-18 sent none.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday()`. The regression tests in `tests/case/test_case_scheduled.py` fail when the old comparison is restored.

**Evening TypeError (missing `triage_at`)**
- **Cause:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Cases with no `triage_at` raised a TypeError, about three times each evening. The likely path is `reopen_button_click` in the Slack interactive handlers. It sets the case to triage directly, skipping the flow that stamps `triage_at`. The logs have no case IDs, so I couldn't confirm the exact cases.
- **Fix:** the job counts from `case.triage_at or case.created_at`. Two new tests cover a case with no `triage_at`: one 14 days old gets the Monday reminder, and one 2 days old does not. The fallback test fails without the fallback.

**Status:** the fixes and tests are uncommitted in the working tree. The test suites for `tests/case` and `tests/case_cost` pass (39 tests). The reopen handler still bypasses the transition flow, which I left as is.

```
FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
```