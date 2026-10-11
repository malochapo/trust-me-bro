**Recap**

- **Symptom:** from mid-August, assignees stopped getting the weekly Monday reminders for long-running triage and stable cases. The daily triage reminders kept working.
- **Root cause:** commit `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12) added a helper, `_is_reminder_day()`, that compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the helper was always false. The close and stable reminder jobs both use it, so neither could send. The daily triage reminder doesn't use it.
- **Deploy:** the logs show only two deploys in the window. Image `main-b05613b5` ran from 2025-07-30 and was replaced by `main-81d8ae42` on 2025-08-13 at ~16:40 UTC. The new image contains the refactor.
- **Timeline:** reminders were sent on Mondays 07-28, 08-04 and 08-11. Monday 08-18 was the first Monday after the deploy, and nothing was sent.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. A parametrized test over a full week fails on the old code and passes on the new.
- **Separate nightly TypeError:** `case_close_reminder` subtracted `case.triage_at` from the current time. Cases that never went through a status transition have no `triage_at`, so the subtraction raised and the case was skipped. It predates the outage and wasn't connected to it. The job now counts from `created_at` when `triage_at` is missing, and three tests cover that. `tests/case` passes (25 tests).
- **Still open:** neither fix is committed, and neither is deployed, so reminders won't resume until a build with both goes out. `case_stable_reminder` still skips cases with no `stable_at` without sending anything.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at