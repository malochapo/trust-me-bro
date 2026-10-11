**Recap**

- **Symptom:** Weekly close and stable reminders stopped after the 2025-08-13 deploy. Daily triage reminders kept going because that job has no weekday check.
- **Root cause:** Commit `c509d45e` ("refactor(case): share the weekly reminder check") replaced `date.today().isoweekday() == 1` with `== calendar.MONDAY`. `isoweekday()` is 1-based and `calendar.MONDAY` is 0, so `_is_reminder_day()` was always False. Both weekly jobs gate on it.
- **Deploy:** `main-81d8ae42`, started 2025-08-13 16:40 UTC. `c509d45e` is in that image and not in the previous one, `main-b05613b5`. The first Monday under the new image was 2025-08-18, and its run logged no weekly sends.
- **Fix:** `_is_reminder_day()` now uses `date.today().weekday()`. Regression test: `tests/case/test_case_scheduled.py::test_is_reminder_day`. It fails on the old line and passes on the fix.
- **Nightly TypeError:** `case_close_reminder` computed `datetime.utcnow() - case.triage_at`. Cases that reach Triage without `triage_at` fail every evening. The likely source is the Slack reopen button, which sets the status to Triage without running the transition that writes `triage_at`. I haven't confirmed this against production data. The job now counts from `created_at` when `triage_at` is NULL, with tests.
- **Open items:**
  - The reopen button still skips the transition, so new cases can keep getting NULL `triage_at`.
  - `case_stable_reminder` has the same missing-timestamp problem with `stable_at`. I didn't change it.
  - Reminder sends aren't logged, so the 2025-08-18 miss comes from the code path and the absence of send logs rather than a direct record.
  - All fixes are uncommitted in the working tree.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at