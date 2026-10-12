**Weekly Monday reminders (case close and stable reminders)**

Monday reminders stopped because of an off-by-one in the weekday check. `_is_reminder_day` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it never matched. Commit `c509d45e` introduced this on 2025-08-12, and it shipped in image `main-81d8ae42` on 2025-08-13. The fix uses `weekday()`. Two regression tests in `tests/case/test_case_scheduled.py` fail without it.

**Nightly TypeError in the case close reminder**

`case_close_reminder` subtracted `case.triage_at` from the current time. `triage_at` is only set when a case moves into triage through `flows.py`, so cases that got into triage another way had a null value and raised a TypeError. The per-case handler caught it, so those cases were silently skipped. The job now counts from `triage_at`, or from `created_at` when `triage_at` is missing. A test covers this case.

**Signal snoozing and deduplication (from the last investigations)**

- A deduplication window stopped working. Commit `917a0b7b` changed `f.window` from minutes to seconds. The UI labels it in minutes, so a window of 30 became 30 seconds. I restored minutes and changed the API defaults so their effective duration is the same. A regression test covers this.
- Snoozing broke for signals with an expired snooze filter. Commit `086dc910` changed an expired filter's `continue` into `break`, so later snooze filters were never checked. I restored `continue` and added a regression test.
- Canary signals are excluded from deduplication by `a348bbd2`, which was a deliberate fix, not a regression.

**Test status:** the signal suite passes. The full suite has 8 failures in `tests/ai`, `tests/database`, and `tests/entity`. They also fail with my changes stashed, and I haven't investigated them.

**Not committed:** everything above is uncommitted in the working tree.

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