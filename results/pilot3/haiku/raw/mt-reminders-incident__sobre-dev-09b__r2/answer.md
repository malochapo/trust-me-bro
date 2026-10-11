Here is the recap for the incident report. Everything in it comes from the logs and the repo history I checked earlier.

## Recap

**Summary:** Since the 2025-08-13 deploy, the weekly Monday reminders for long-running triage and stable cases have not been sent. Daily triage reminders kept working. The bug is in a helper that was refactored on 2025-08-12.

**Root cause:** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) against `calendar.MONDAY` (Monday = 0). The comparison was never true, so `case_close_reminder` and `case_stable_reminder` never sent their weekly reminders. The refactor was `c509d45e` ("refactor(case): share the weekly reminder check", 2025-08-12). The original inline check was `isoweekday() == 1`, which was correct.

**Timeline:**
- 2025-08-11 (Monday): last successful weekly reminders, sent by the image built before the refactor.
- 2025-08-13 16:40 UTC: scheduler restarted on `main-81d8ae42`, which includes `c509d45e`.
- 2025-08-18 (Monday): first missed run. Only triage and incident-close reminders were sent that day.

**Fix:** `date.today().weekday() == calendar.MONDAY`. Regression tests cover every weekday and the end-to-end stable job on a Monday and a Tuesday. Without the fix, the Monday tests fail.

**Separate evening TypeError:** `case_close_reminder` subtracted `case.triage_at` from `utcnow()`. Cases that reached Triage without going through the flow (`src/dispatch/case/flows.py:594-596` is the only place `triage_at` is set) have it as `None`. The error was caught per case, so it was logged each evening and only those cases were skipped. The job now falls back to `case.created_at`. Two tests cover it: one checks that the reminder is sent, and one checks that a too-new case doesn't raise or get reminded.

**Status:** The fixes to `scheduled.py` and the new test file are uncommitted and not deployed. Also not changed: `case_stable_reminder` still skips stable cases with no `stable_at`, which I didn't change because you only asked about the close job.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at