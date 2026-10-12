**Weekly Monday reminders (close and stable cases)**
The reminder check compared `calendar.MONDAY`, which is 0, with `date.isoweekday()`, which is 1 for Monday, so it never matched. Commit `c509d45e` (2025-08-12) introduced that comparison. It shipped in image `main-81d8ae42`, deployed 2025-08-13. The last Monday with reminders was 2025-08-11 (6 sent). I fixed `_is_reminder_day()` to compare against 1, and added `tests/case/test_case_scheduled.py`, which fails if the comparison is reverted.

**Nightly TypeError from the close reminder job**
`case_close_reminder` subtracted `case.triage_at` from the current time without checking for NULL. The scheduler log has 80 of these errors from 2025-07-28 to 2025-08-20. The job now counts from `triage_at`, falling back to `created_at` when it is missing. The test covers both a case created 8 days ago (one reminder) and one created 3 days ago (none). I confirmed that `reopen_button_click` can set Triage without writing `triage_at`, but I haven't checked production data to see how many cases are affected. I haven't changed the reopen path.

**Deduplication window**
Commit `917a0b7b` (2025-08-14) read `SignalFilter.window` as seconds, although the UI labels it in minutes. A filter window of 30 became 30 seconds. The fix multiplies by 60, and `test_filter_actions_deduplicate_window_is_in_minutes` covers it.

**Snoozing**
Commit `086dc910` (2025-08-07) changed the expired-snooze branch from `continue` to `break`. An expired filter earlier in the list stopped the check, so a valid snooze filter after it was never applied. The fix restores `continue`, and `test_filter_actions_snooze_expired_filter_does_not_hide_valid_one` covers it.

**Canary signals**
Commit `a348bbd2` (2025-05-29) excluded canary instances from deduplication.

**Open items**
- The `window` column default (`60 * 60`) and the Pydantic default (`600`) are now read as minutes. New filters created without a window would get 3600 or 600 minutes. I left them unchanged and need a decision.
- `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` was introduced in `7a9fe810` (2025-06-19), which also changed the default from 60 to 45 minutes.
- Nothing is committed yet. The changes are in the working tree.

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