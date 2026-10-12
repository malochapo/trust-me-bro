## Recap

**Symptom:** Since mid-August, assignees stopped getting the Monday reminders for long-running triage and stable cases. Daily triage reminders kept arriving.

**Root cause:** Commit `c509d45e` ("refactor(case): share the weekly reminder check") moved the Monday test into `_is_reminder_day()` and compared the wrong weekday numbering. The original `date.today().isoweekday() == 1` was correct. The refactor replaced `1` with `calendar.MONDAY`, which is `0` in Python. `isoweekday()` gives Monday as `1`, so the check was never true and the weekly reminders never sent. The helper gates both `case_close_reminder` (triage) and `case_stable_reminder` (stable), which is why both stopped and the daily triage reminder did not.

**Deploy:** `registry.example.com/dispatch:main-81d8ae42` started on the scheduler at 2025-08-13T16:40:06Z. That commit contains `c509d45e`. The first Monday on that image was 2025-08-18. The 2025-08-18 scheduler run logged no weekly reminder sends.

**Fix:** `src/dispatch/case/scheduled.py` now uses `date.today().weekday() == calendar.MONDAY`. The regression test in `tests/case/test_case_scheduled.py` pins each day of one week and fails on the old line.

**Second issue, the nightly TypeError:** `case_close_reminder` subtracted `case.triage_at` from `utcnow()`, and `triage_at` was `NULL` on some triage cases. The likely source is that the 2022 migration that added the column didn't backfill existing rows. The Slack reopen button also moves a case to triage without running the transition flow, which can leave the timestamp unset. The logs don't name the affected cases, so this is inferred, not confirmed against production data. The fix counts from `created_at` when `triage_at` is missing, and the new tests cover that path.

**Verification:** The case suite passes (27 tests). The full suite gives 371 passed, 4 skipped, and 8 failed. The 8 failures are in the AI, database, and entity tests, and they also fail without my changes.

**Not done:** Nothing is committed. The reopen-button path is still unfixed. Cases that already had `NULL` `triage_at` aren't backfilled.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at