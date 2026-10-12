Here is the recap for the weekly report. All of it is uncommitted and undeployed.

**1. Missing Monday reminders (long-running triage and stable cases)**
- **Cause:** the helper `_is_reminder_day` in `src/dispatch/case/scheduled.py` was meant to return true only on Mondays. It compared `date.today().isoweekday()` with `calendar.MONDAY`. `calendar.MONDAY` is 0, but `isoweekday()` numbers Monday as 1, so the check was never true on a Monday. It was true on Sundays, but the Sunday run never found cases old enough to need a reminder.
- **Introduced by:** commit c509d45e (2025-08-12).
- **Shipped by:** image `main-81d8ae42`, started on 2025-08-13 at 16:40Z. The first Monday after the deploy was 2025-08-18, and that is when the reminders stopped. The 2025-08-11 Monday came before the deploy.
- **Fix:** the helper now uses `weekday() == calendar.MONDAY`.
- **Tests:** a regression test checks a Monday, a Tuesday and a Sunday, and covers both reminder jobs.

**2. Nightly TypeError in the case close reminder**
- **Cause:** the job subtracts `case.triage_at` from the current time, and that field is empty for some cases. Only the status-transition flow sets it, so a case created directly in triage never gets one.
- **Fix:** the job now counts from `case.triage_at or case.created_at`, so those cases get their weekly reminder.
- **Tests:** a 10-day-old case with no `triage_at` gets the reminder, and a 2-day-old one does not.
- **Not verified:** I inferred the cause from the code, not from the database.
- **Not done:** I didn't backfill existing cases or set `triage_at` on the other transition paths.

**3. Signal snooze and deduplication changes since 2025-05-22**
- a348bbd2 stops deduplicating canary signals, and ignores earlier canary instances when matching.
- 7a9fe810 makes the default window for signals without filters configurable. It was 1 hour and is now 45 minutes unless the setting is changed.
- 086dc910 changed snooze behaviour. An expired snooze filter now stopped the loop instead of being skipped, so a valid filter listed after it was never checked. I fixed it and added a test.
- 917a0b7b changed a filter's window from minutes to seconds, so a UI setting of 30 became 30 seconds. I fixed it by multiplying by 60 and added a test.
- The model default for `SignalFilter.window` (`60*60`, commented as seconds) is unchanged. Read as minutes, it is 60 hours.
- 4474af25 and 5e136d7b do not affect the decisions.
- I ran only the two test files I touched, not the full suite.

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