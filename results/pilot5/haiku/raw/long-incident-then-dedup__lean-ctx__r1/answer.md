**Weekly reminder and case close TypeError (today's first two investigations)**

- **Missing weekly reminders:** Since the 2025-08-13 deploy, the weekly close and stable reminders have not gone out. The cause is in `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. It compared `date.today().isoweekday()` (Monday is 1) with `calendar.MONDAY` (which is 0), so the check never matched. The bug was introduced by `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") and shipped in `main-81d8ae42`, which started on 2025-08-13 at 16:40 according to the scheduler log. The fix uses `date.today().weekday()`. A parametrized test covers the Monday/Sunday boundary.
- **Nightly TypeError:** The close job computed `datetime.utcnow() - case.triage_at`. Some cases were in `triage` status with `triage_at` NULL, because a few Slack paths set the status directly and skip the flow that stamps `triage_at`. The fix counts from `created_at` when `triage_at` is missing, and a parametrized test covers that.

**Deduplication, snoozing, and the default window (second batch of reports)**

- **Deduplication windows:** `917a0b7b` (2025-08-14) changed how a filter's window is read, from minutes to seconds. The UI sets windows in minutes, so a window of 30 became 30 seconds, and instances ten minutes apart opened separate cases. The helper now takes minutes again, and a regression test covers the 10- and 45-minute cases.
- **Snoozing:** `086dc910` (2025-08-07) changed the expired-snooze branch from `continue` to `break`. An expired snooze stopped the loop, so a valid snooze listed after it was never checked. The branch is back to `continue`, and a regression test covers it.
- **Canary signals:** `a348bbd2` (2025-05-29, "fix(signal): don't dedup on canary signals") is the change to how canary signals are deduplicated. It skips them and excludes them as matches. I didn't change it.
- **Default window:** Signals without any filter are grouped over 45 minutes. Before `7a9fe810` (2025-06-19) it was a fixed 1 hour. The value comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which is in minutes.

**Status:** Nothing is committed. The full suite is 373 passed, 4 skipped, and 8 failed. The 8 failures predate this work (6 in `tests/ai/test_ai_service.py`, plus `test_restricted_case_filter_with_test_data` and `test_find_entities_with_field_only`). Not yet done: the stable-reminder path still has no `created_at` fallback, and the column default `window = 60 * 60` is now read as 60 hours. I flagged both earlier.

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