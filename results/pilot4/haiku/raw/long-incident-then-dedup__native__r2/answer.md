**Weekly reminder investigation.** Monday case-close and case-stable reminders stopped after commit `c509d45e` ("refactor(case): share the weekly reminder check"). That commit made `_is_reminder_day()` compare `date.today().isoweekday()` with `calendar.MONDAY`, which is 0. ISO weekday numbering starts at 1, so the check was never true. The commit shipped in image `main-81d8ae42`, deployed 2025-08-13 16:40Z. The first Monday without reminders was 2025-08-18, since 2025-08-11 came before the deploy. I fixed it to use `weekday()` and added `tests/case/test_case_scheduled.py`, which covers the weekday check and the reminder jobs.

**Nightly TypeError.** The close-reminder job subtracted `case.triage_at` from the current time. `triage_at` is nullable and was only set when a case moved into triage. The 2022 migration that added it did not backfill existing cases, so a case that was already in triage has no value and the subtraction fails. The job now counts from `created_at` when `triage_at` is missing, and it still prefers `triage_at` when it is set. The logs show the errors stopped after 2025-08-12, and I did not identify the specific case from data. I added three tests for this.

**Signal filter regressions.** Three separate bugs:
- `917a0b7b` read per-filter dedup windows as seconds, but the UI sets them in minutes. A 30-minute window became 30 seconds. I changed the window back to minutes, fixed the model column default from 3600 to 60, and added a parametrized regression test.
- `086dc910` changed the expired-snooze branch from `continue` to `break`, so a valid snooze filter after an expired one was never applied. I restored `continue` and added a regression test.
- `a348bbd2` made canary signals skip deduplication, both as the instance being checked and as a match for others.

Test status: `python -m pytest tests/signal tests/case tests/case_cost` gives 76 passed and 1 skipped. Nothing is committed.

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