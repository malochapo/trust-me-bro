## Recap

**Missing weekly reminders**
- Commit `c509d45e` (2025-08-12, a "refactor") moved the Monday check into `_is_reminder_day()`. It changed `date.today().isoweekday() == 1` to `isoweekday() == calendar.MONDAY`.
- `calendar.MONDAY` is 0 and `isoweekday()` returns 1 on Monday, so the check was never true. `case_close_reminder` (long-running triage cases) and `case_stable_reminder` (stable cases) both use it, so neither sent again. The daily triage reminder doesn't use it, which is why those kept arriving.
- It reached production with the rollout around 2025-08-13 16:40 UTC, which replaced `main-b05613b5` with `main-81d8ae42`. Reminders were sent normally on Monday 2025-08-11 from the old pod. The first Monday after the rollout was 2025-08-18, and the scheduler log has no "Case close reminder sent" lines that day.
- Fix: `_is_reminder_day()` now uses `date.today().weekday() == calendar.MONDAY`, with a regression test. The fix is not committed or deployed yet.

**Evening TypeError**
- `case_close_reminder` computed `utcnow() - case.triage_at`. Cases moved to Triage without running the transition flow (for example the Slack handler at `plugins/dispatch_slack/case/interactive.py:1427`) never get a `triage_at`, so the subtraction hit `None`. I confirmed that one path in the code, not the individual cases in the logs.
- Fix: the job now counts from `triage_at`, or from `created_at` when `triage_at` is missing, so those cases get their weekly reminder. The fix is covered by a new test and is also uncommitted and undeployed.

**Unrelated:** a database outage on 2025-08-15 around 14:40 UTC ("Connection refused") shows up in the same logs. It had nothing to do with the missing reminders.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at