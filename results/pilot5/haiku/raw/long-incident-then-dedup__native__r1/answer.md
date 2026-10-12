Both investigations are done. The changes are uncommitted in the working tree. Test results: `python -m pytest tests/signal tests/case` gives 59 passed, 1 skipped.

**Monday reminders (weekly case reminders missing)**
- The weekday check in `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it never matched. It went in with `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check"). The deploy that shipped it is image `main-81d8ae42`, started 2025-08-13 in `api.log`.
- Fix: compare with `date.today().weekday()`. Regression test: `test_is_reminder_day` in `tests/case/test_case_scheduled.py`. It fails on the old code and passes now.
- The api log only shows web containers. I didn't find the scheduler's own deploy record, so the image tag is the web deploy that contains `c509d45e`.

**Evening TypeError (case close reminder)**
- `case.triage_at` is NULL for some cases in triage. Some paths set triage without running the transition flow that stamps `triage_at`, most clearly the reopen button handler in `interactive.py`. The job then computes `datetime.utcnow() - None`, the error is caught per case, and the case gets no reminder.
- Fix: the job counts from `case.triage_at or case.created_at`. Three tests in `tests/case/test_case_scheduled.py` cover missing `triage_at`, a recent case, and `triage_at` winning over `created_at`.
- Not confirmed: which production cases lack `triage_at`, since the logs have no case IDs. The paths that skip the flow are still there.

**Deduplication window in minutes**
- `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation") changed per-filter windows from minutes to seconds. A window of 30 became 30 seconds, so a 10-minute gap never grouped. The UI says "Window (minutes)".
- Fix: the window helper takes minutes again, so stored filters need no edits. Regression test: `test_filter_actions_deduplicate_window_is_in_minutes`.

**Snoozing after an expired snooze**
- `086dc910` (2025-08-07, "refactor(signal): simplify snooze filter checks") changed `continue` to `break` when a snooze filter had expired, so later active snooze filters were never checked.
- Fix: restored `continue`. Regression test: `test_filter_actions_snooze_after_expired_snooze`.

**Canary signals**
- `a348bbd2` (2025-05-29, "fix(signal): don't dedup on canary signals (#6026)") makes canary instances skip deduplication and excludes them from matches.

**Default window**
- Signals without a filter group instances over 45 minutes. The commit `7a9fe810` made this configurable; it was hard-coded at 1 hour before.

**Still open**
- The `window` column default in `models.py` is `60 * 60`, which under the minutes reading is 60 hours. It needs a migration to change, so I left it.
- The stable-case job still skips cases without `stable_at`. I didn't change it.

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