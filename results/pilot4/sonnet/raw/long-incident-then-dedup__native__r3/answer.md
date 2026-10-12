Four things were wrong. Two came from "refactor" commits that changed behaviour, one affected stored data the code reads, and one was a gap in how the job reads case timestamps. All four are fixed and have regression tests. Nothing is committed, and I only ran the signal tests and the new case-scheduler tests, not the full suite.

**1. Weekly Monday reminders stopped (long-running triage and stable cases)**
- Commit `c509d45e` (2025-08-12, "share the weekly reminder check") moved the Monday check into a new helper, `_is_reminder_day`, in `src/dispatch/case/scheduled.py`.
- The old inline check was `date.today().isoweekday() == 1`. The helper compares `isoweekday()` (Monday is 1) to `calendar.MONDAY` (which is 0), so it was true on Sundays and never on Mondays. Both `case_close_reminder` and `case_stable_reminder` use the helper, so both weekly reminders stopped.
- The commit shipped to production as image `registry.example.com/dispatch:main-81d8ae42`, started at 2025-08-13 16:40Z. The first Monday after that is 2025-08-18, the first one without reminders.
- Daily triage reminders kept working because they never use that helper.
- The fix compares `date.today().weekday()` to `calendar.MONDAY`. The new test file `tests/case/test_case_scheduled.py` covers each day of the week.

**2. Evening `TypeError` in the case close reminder**
- The job counts how long a case has been in triage from `triage_at`, which is only set on status transitions. Cases created directly in triage, or before the column existed, have none.
- The subtraction raised the `TypeError`, and the per-case `try/except` logged it and skipped the case, so those cases never got a reminder.
- It now counts from `triage_at or created_at`, with tests for both paths. I left `case_stable_reminder` as it was, with its `stable_at` guard.

**3. Deduplication windows far too short**
- Commit `917a0b7b` (2025-08-14) added a seconds-based helper and passed it the filter window unchanged. The UI and the stored values are in minutes, so a window of 30 minutes became 30 seconds.
- `filter_dedup` now converts with `f.window * 60`, so existing filters work without edits. I also corrected the misleading column comment.
- The new test uses an earlier instance 10 minutes old. A 30-minute window groups it and a 5-minute window does not.

**4. Snoozing broken when an expired filter comes first**
- Commit `086dc910` (2025-08-07) changed an expired snooze filter's `continue` to `break` in `filter_snooze`, which ended the loop. A valid snooze filter listed after an expired one was never checked.
- It is back to `continue`. The new test puts an expired filter before a valid one and expects the instance to be snoozed.

**Canary signals and the default window**
- Commit `a348bbd2` (2025-05-29) stops canary signals from being deduplicated and keeps canary instances out of the candidates.
- Commit `7a9fe810` (2025-06-19) made the default window for signals without filters configurable. It dropped the default from 1 hour to 45 minutes without saying so in the commit message.

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