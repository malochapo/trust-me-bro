**Recap**

- **Symptom:** weekly Monday reminders for long-running triage and stable cases stopped in mid-August. The daily triage reminders kept arriving.
- **Root cause:** commit `c509d45e`, "refactor(case): share the weekly reminder check" (2025-08-12), moved the Monday check into a helper, `_is_reminder_day()`. The helper compared `date.today().isoweekday()` (Monday is 1) against `calendar.MONDAY` (which is 0). That is never true, so neither weekly reminder was sent and nothing was logged.
- **Deploy:** the scheduler and web pods restarted on 2025-08-13 at about 16:40Z with image `main-81d8ae42`, which contains the refactor. The Monday reminders on 08-04 and 08-11 were sent on the old image, `main-b05613b5`. The first Monday after the deploy was 2025-08-18, and no case close reminders were sent that day.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. I added a test covering all seven weekdays. With the old code, the Monday case fails.
- **Separate bug, the evening TypeError:** `case_close_reminder` subtracted `case.triage_at`, which is empty for cases that never went through the transition into triage. The job logged a TypeError for them every evening and sent them no reminder. It now counts from `created_at` when `triage_at` is missing, and I added tests for that.
- **Not changed:** `case_stable_reminder` still skips cases without `stable_at` instead of counting from `created_at`.
- **Not yet in production:** both fixes are uncommitted and not deployed, so the reminders stay off until a new image ships.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at