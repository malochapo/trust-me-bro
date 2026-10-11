**Recap**

- **Symptom:** from mid-August, assignees stopped getting the weekly Monday reminders for long-running triage and stable cases. The daily triage reminders kept arriving.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) moved the Monday check into `_is_reminder_day()`. The helper compares `date.today().isoweekday()`, which runs 1 to 7, against `calendar.MONDAY`, which is 0. The comparison was never true, so `case_close_reminder` and `case_stable_reminder` never sent anything. The daily triage reminder doesn't use the helper, which is why it kept working.
- **Deploy:** image `registry.example.com/dispatch:main-81d8ae42` started on 2025-08-13 at 16:40Z on the scheduler and web pods. It replaced `main-b05613b5`, which had been running since 2025-07-30.
- **Evidence:** "Case close reminder sent" appears 4 times on 07-28, 6 on 08-04 and 5 on 08-11. It appears 0 times on 08-18, and the jobs finish in about 0.03 to 0.05 seconds with no sends.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Regression tests are in `tests/case/test_case_scheduled.py`, and three of them fail on the old code.
- **Second issue (the evening `TypeError`):** `case_close_reminder` computed `utcnow() - case.triage_at`. `triage_at` is only set by the triage transition flow, so cases created directly in triage status, or created before the column existed, have none. Those cases logged an error every evening and could never get a reminder. The job now falls back to `created_at`, with a test.
- **Not committed:** all the changes are in the working tree.

The 2025-08-11 reminders were sent. The 2025-08-13 deploy was the first to ship the bug, so 2025-08-18 was the first Monday that went unsent.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at