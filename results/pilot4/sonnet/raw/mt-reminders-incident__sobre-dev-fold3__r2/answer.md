**Recap**

- **Symptom:** from mid-August, assignees stopped getting the weekly Monday reminders for long-running triage and stable cases. The daily triage reminders kept arriving.
- **Root cause:** commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") added a helper, `_is_reminder_day()`. It compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (Monday is 0). The check could never be true on any day, so `case_close_reminder` and `case_stable_reminder` stopped sending. The daily triage reminder doesn't use the helper, so it was unaffected.
- **Deploy:** image `main-81d8ae42` went to production on 2025-08-13 at about 16:40Z. The previous image, `main-b05613b5`, was running from 2025-07-30 and didn't have the helper.
- **Evidence:** the scheduler log shows close reminders sent on Mondays 07-28, 08-04 and 08-11. Monday 08-18 is the first Monday after the deploy, and it has no case close or stable reminders.
- **Fix:** the helper now uses `weekday() == calendar.MONDAY`. I added a regression test that fails on the old code.
- **Second issue:** the evening `TypeError` came from triage cases with no `triage_at`. That timestamp is only set in the New→Triage and Closed→Triage transition flow, so cases that entered triage another way never had it. The close reminder now counts from `created_at` when `triage_at` is missing. I added tests, and all of `tests/case` passes (23).
- **Status:** both fixes are uncommitted in the working tree. I haven't committed or deployed anything. `case_stable_reminder` still skips cases with no `stable_at`, which I left alone.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at