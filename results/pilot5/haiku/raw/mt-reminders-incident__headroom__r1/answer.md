**Recap**

- **Weekly reminders stopped after the 2025-08-13 deploy.** Commit `c509d45e` moved the Monday check into `_is_reminder_day()`, which compared `isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). The comparison never matched, so the weekly triage and stable reminders stopped. Daily triage reminders don't use the check and kept arriving. The logs show 5 close reminders on Monday 2025-08-11, before the commit, and none on Monday 2025-08-18.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`. Regression test: `tests/case/test_case_scheduled.py::test_is_reminder_day`. It fails on the old line and passes on the fix.
- **Evening TypeError:** `case_close_reminder` subtracted from `case.triage_at`, which is `None` for cases that were moved to triage through three Slack handlers that set the status directly and skip the transition flow. The error was caught and the case skipped, so those cases never got a reminder. **Fix:** the job now counts from `case.triage_at or case.created_at`. Two new tests run the real job on a Monday. One checks that an 8-day-old case gets a reminder, and the other that a 2-day-old case does not. The 8-day test fails without the fallback, with the same `TypeError`.
- **Verification:** `python -m pytest tests/case` passes 20 of 20 against the local PostgreSQL.
- **Status:** both fixes are uncommitted in the working tree, and nothing has been deployed. The Slack handlers that skip `triage_at` are still open. Setting it there would be the proper follow-up.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at