**Recap**

- **Symptom:** since mid-August, assignees stopped getting the Monday reminders to close long-running triage and stable cases. The daily triage reminders kept arriving because they run in a separate job with no Monday check.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) added a shared `_is_reminder_day()` helper. It compared `date.today().isoweekday()`, where Monday is 1, to `calendar.MONDAY`, which is 0, so it was never true. Both `case_close_reminder` and `case_stable_reminder` use the helper, so neither could send its weekly reminder.
- **Deploy:** the scheduler and API pods moved to image `main-81d8ae42` at 2025-08-13T16:40Z, and that image contains `c509d45e`. The previous image, `main-b05613b5`, did not.
- **Log evidence:** "Case close reminder sent" lines appear on 07-28 (4), 08-04 (6) and 08-11 (5). There are none after that, and the 08-18 18:00 run logged only the incident close reminder.
- **Fix:** the helper now uses `date.today().weekday() == calendar.MONDAY`. A new test pins the date and checks that only Mondays return true.
- **Second issue, the evening TypeError:** `case_close_reminder` subtracted `case.triage_at`, which is `None` for cases that never went through triage. The job now falls back to `created_at`, and there is a test for it. I left the stable-case job unchanged, so it still skips cases with no `stable_at`.
- **State:** both fixes and their tests are in the working tree and not committed. The 9 tests in `tests/case/test_case_scheduled.py` pass, but I didn't run the full suite. Nothing is deployed yet.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at