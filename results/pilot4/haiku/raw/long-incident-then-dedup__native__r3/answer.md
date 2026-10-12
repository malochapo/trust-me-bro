## Recap

**Weekly reminders (Monday).** Assignees stopped getting weekly reminders to close long-running triage and stable cases after the deploy of 2025-08-13. The cause was `_is_reminder_day()` in `src/dispatch/case/scheduled.py`. It compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it never matched. Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") introduced the mismatch, and it shipped in image `main-81d8ae42`. The fix uses `weekday()`. A regression test in `tests/case/test_case_scheduled.py` fails on the old code and passes with the fix.

**Evening TypeError.** The close-reminder job did `datetime.utcnow() - case.triage_at`. Cases in triage with no `triage_at` raised a TypeError, which the per-case `try` caught, so those cases never got a reminder. The job now counts from `created_at` when `triage_at` is missing. Three job-level tests cover it: the missing-field case fails on the old code, a recent case is skipped, and a set `triage_at` still wins. The root cause of the null `triage_at` rows is not confirmed. The logs have no case IDs, and I had no database access. The likely paths are transitions into triage that skip `case_triage_status_flow`, and cases from before the 2022 column was added.

**Deduplication windows.** The UI labels a filter's window "minutes", but commit `917a0b7b` (2025-08-14) started reading it as seconds. A 30-minute window became 30 seconds. The fix restores minutes and corrects the model default and comment. Two regression tests cover it: one that groups instances ten minutes apart, and one that excludes an instance 40 minutes old. The first fails with the seconds reading.

**Snoozing.** Commit `086dc910` (2025-08-07) changed the expired-filter check in `filter_snooze` from `continue` to `break`. An expired snooze filter ahead of a valid one stopped the loop, so the valid one never applied. The fix restores `continue`. A regression test puts an expired filter first and a valid one second. It fails with `break` and passes with `continue`.

**Test status.** `python -m pytest` gives 372 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py`, `tests/database/test_service.py`, and `tests/entity/test_entity_service.py`. They also fail on the original code, so they predate this work. Nothing is committed. The working tree has the changes to `src/dispatch/case/scheduled.py`, `src/dispatch/signal/models.py`, `src/dispatch/signal/service.py`, `tests/signal/test_signal_service.py`, and the new `tests/case/test_case_scheduled.py`.

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