**Recap**

- **Symptom:** since mid-August, assignees stopped getting the Monday reminders for long-running triage and stable cases. The daily triage reminders kept arriving.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) added the helper `_is_reminder_day()`. It compared `date.today().isoweekday()` (Monday = 1) to `calendar.MONDAY` (0), so it was never true. The close and stable reminder jobs ran every evening but never sent anything, and nothing was logged.
- **Deploy:** image `registry.example.com/dispatch:main-81d8ae42` replaced `main-b05613b5` on 2025-08-13T16:40Z, on both the scheduler and web pods.
- **Evidence:** Mondays 07-28, 08-04 and 08-11 sent reminders. Monday 08-18 sent none. Daily triage reminders continued through 08-20.
- **Fix:** the helper now uses `date.today().weekday()`. The regression test checks the helper against every weekday and checks both jobs on a Monday and a Tuesday. It fails without the fix.
- **Evening TypeError:** `case_close_reminder` subtracted `case.triage_at`, which is `None` for cases created directly in triage. Only the triage status flow sets it. The job now falls back to `created_at`, and a test covers that.
- **Open items:** `case_stable_reminder` still skips cases with no `stable_at`, which I left alone. Nothing is committed yet.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at