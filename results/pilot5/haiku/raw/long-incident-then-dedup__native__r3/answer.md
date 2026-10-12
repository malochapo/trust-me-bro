Here is the recap for both investigations. The working-tree fixes are not committed yet.

**Weekly reminders (weekday bug)**
- The weekly close and stable reminders stopped after the 2025-08-11 run. The daily triage reminders kept arriving.
- The Monday check used `isoweekday()`, which numbers Monday as 1. It was compared with `calendar.MONDAY`, which is 0, so the check could never be true. Commit `c509d45e` (2025-08-12) introduced this. It shipped in the image `main-81d8ae42`, which was running on the scheduler by 2025-08-13.
- Fix: `_is_reminder_day` now uses `weekday()`. A regression test checks that 2025-08-11 is a reminder day and that Tuesday, Friday and Sunday are not.
- The first Monday with no reminders sent was 2025-08-18.

**Evening TypeError (case close reminder)**
- The nightly close reminder job failed with `datetime - NoneType` for cases in triage with no `triage_at`. Only the triage flow sets that field. A candidate path is the Slack reopen button, which sets the status to triage directly. I have not checked which production cases are affected.
- Fix: the job counts from `created_at` when `triage_at` is missing. Two tests cover the fallback and the case where `triage_at` is set.
- Not changed: the stable reminder still skips cases with no `stable_at`.

**Signal deduplication and snoozing**
- Dedup windows: commit `917a0b7b` (2025-08-14) changed the window from minutes to seconds. A window of 30 meant 30 seconds, so instances ten minutes apart opened separate cases. The fix restores minutes, which is what the UI labels. Existing stored values work unchanged, and a regression test covers it.
- Snoozing: commit `086dc910` (2025-08-07) changed an expired snooze filter from `continue` to `break`. The loop stopped at the first expired filter, so a valid filter after it never applied. The fix restores `continue`, and a regression test covers it.
- Canary signals: commit `a348bbd2` (2025-05-29) stopped canary signals from being deduplicated and excluded them from matching. No change was needed here.
- Default window: signals with no filter are grouped over 45 minutes. The setting `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` controls it, and it defaults to 45.
- Not changed: the model defaults for `SignalFilter.window` (3600 and 600) now read as 60 hours and 10 hours.

The full test suite shows the same 8 failures as before, all of which also fail on unmodified code. Nothing is committed.

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