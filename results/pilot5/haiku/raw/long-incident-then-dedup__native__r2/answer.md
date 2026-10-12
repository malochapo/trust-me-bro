Here is the recap for the weekly report.

**Monday reminders (case close and stable)**
- The weekday check compared `isoweekday()`, where Monday is 1, with `calendar.MONDAY`, where Monday is 0. Monday reminders never went out.
- The check was introduced in `c509d45e` (2025-08-12) and deployed in image `main-81d8ae42` on 2025-08-13. Monday 2025-08-11 ran on the previous image, so 2025-08-18 is the first missed Monday.
- Fix: `date.today().weekday() == calendar.MONDAY` in `_is_reminder_day()`, with a regression test in `tests/case/test_case_scheduled.py`.

**Evening TypeError (case close reminder)**
- Cases in triage with no `triage_at` raised `TypeError` on the subtraction, so each one was logged and skipped every evening.
- Fix: count from `created_at` when `triage_at` is missing, with job-level tests.
- Not confirmed: how these cases got a null `triage_at`. The Slack reopen button bypasses the status flow that sets it, but I could not tie the logged cases to it, and the affected records have not been identified.

**Signal filters (same batch of changes)**
- Dedup windows: `917a0b7b` read a filter's window as seconds, but the UI labels it minutes. A window of 30 looked back 30 seconds. Fixed in `filter_dedup` with `f.window * 60`, with a regression test.
- Snoozing: `086dc910` changed an expired snooze filter from `continue` to `break`, so a valid snooze listed after it was never checked. Restored `continue`, with a regression test.
- Canary: `a348bbd2` (2025-05-29) stopped deduplicating canary signals.
- Default window for signals with no filter: 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES

Nothing is committed. The working tree holds the fixes and tests for all three problems. The full suite has 8 failures in AI, database, and entity tests that also fail on the original code. I did not investigate them.