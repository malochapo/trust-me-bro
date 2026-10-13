## Weekly report: Monday reminders and signal grouping

**1. Missing Monday reminders (case close and stable).** Reminders stopped after the 2025-08-12 change `c509d45e` ("refactor(case): share the weekly reminder check"). It replaced the reminder check with `date.today().isoweekday() == calendar.MONDAY`. `isoweekday()` returns 1 for Monday, but `calendar.MONDAY` is 0, so the check never matched. The code shipped in image `main-81d8ae42`, which started on the scheduler at 2025-08-13 16:40 UTC. The first Monday affected was 2025-08-18. The fix uses `date.today().weekday()`, and the new tests in `tests/case/test_case_scheduled.py` fail on the old logic. I did not commit it.

**2. Evening TypeError in the case close reminder.** The job computed `datetime.utcnow() - case.triage_at`. Some triaging cases have `triage_at` NULL, because only `case_triage_status_flow` stamps it and the Slack reopen button sets the status directly. Subtracting `None` raised the TypeError. The job now counts from `triage_at or created_at`, with a test covering both paths. I could not confirm which production cases are affected, because the logs have no case IDs. The stable reminder has the same gap (`stable_at`) and is still open.

**3. Signal grouping and snoozing.** Three commits since 2025-05-22 caused the reported failures:
- `917a0b7b` treated a filter's dedup window as seconds, but the UI labels it in minutes. A window of 30 became 30 seconds. Fixed in `service.py` (multiply by 60), with a test. Existing filters need no edits.
- `086dc910` changed an expired snooze from `continue` to `break`, so later active snoozes for the same signal were skipped. Fixed back to `continue`, with a test.
- `a348bbd2` made canary signals skip deduplication, and excluded them as dedup targets. This is the intended behavior, and I did not change it.

Tests: `python -m pytest tests/signal tests/case -q` gives 65 passed, 1 skipped. The full suite was not run. The changes are uncommitted in the working tree.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES