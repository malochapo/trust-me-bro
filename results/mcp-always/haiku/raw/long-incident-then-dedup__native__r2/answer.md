**Investigation 1: Monday reminders stopped.** Since mid-August, assignees haven't received the weekly Monday reminders for long-running triage and stable cases. The daily triage reminders still arrived. Commit `c509d45e` (a refactor, 2025-08-12) changed the weekday check in `_is_reminder_day` from `date.weekday()` to `isoweekday()`, which is 1-based. The code compared that against `calendar.MONDAY`, which is 0-based, so the check was never true. The commit shipped with image `main-81d8ae42`, deployed 2025-08-13. The first Monday that went without reminders was 2025-08-18. I fixed the check to use `weekday()` and added tests for it in `tests/case/test_case_scheduled.py`.

**Investigation 2: the case close TypeError.** The `case_close_reminder` job logged a TypeError every evening. The cause is that `triage_at` is `None` for some cases in triage. Those cases reached triage without going through the triage flow, which is the only code that sets `triage_at`. The status dispatcher's catch-all branch for Triage doesn't set it, so a case moved from Stable or Escalated into Triage keeps `triage_at` empty. The job now counts from `created_at` when `triage_at` is missing, and a test covers that case. I haven't confirmed which route produced the cases in production, and the catch-all branch itself is unchanged, pending your decision.

**Deduplication and snoozing.** Three commits changed behavior after 2025-05-22. Two of them broke things and are now fixed in the working tree:
- `917a0b7b` changed the per-filter dedup window from minutes to seconds. A window of 30 meant 30 seconds, so instances ten minutes apart didn't group. The window is back in minutes, matching the UI.
- `086dc910` changed an expired snooze filter from `continue` to `break`. A valid snooze after an expired one in the list was never checked. It's back to `continue`, with a regression test.
- `a348bbd2` is the canary change: canary signals skip deduplication and are excluded from matching. I didn't find a bug in it.

The default grouping window for signals without filters is 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.

**Open items:**
- All fixes are uncommitted in the working tree. Changed files: `src/dispatch/case/scheduled.py`, `src/dispatch/signal/service.py`, `src/dispatch/signal/models.py`, `tests/signal/test_signal_service.py`, and the new `tests/case/test_case_scheduled.py`.
- Eight tests in `ai`, `database`, and `entity` fail on the current tree. They also fail with my signal changes stashed, so they predate this work. I didn't investigate them.
- The model default `window = 3600` and the API default `600` now mean 60 hours and 10 hours. I left them alone, pending your decision.

Summary lines:

```
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
```