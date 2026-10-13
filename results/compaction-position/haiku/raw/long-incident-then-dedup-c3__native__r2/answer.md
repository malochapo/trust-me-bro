**Weekly reminders (Monday close and stable reminders)**

Assignees stopped getting the Monday reminders after the 2025-08-13 deploy. The weekday check compared Python's 1-based `isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true. Commit `c509d45e` introduced this. I changed the check to `.weekday()` and added `tests/case/test_case_scheduled.py`, which fails on the old code. The first missed Monday was 2025-08-18.

Separately, `case_close_reminder` raised a TypeError every evening. `triage_at` is set only when a case transitions into triage, so some triage cases have it empty, and the job subtracted it from the current time. The error fired before the Monday check. The job now counts from `created_at` when `triage_at` is missing. The new test covers this case and the existing `triage_at` path. The exact code path that leaves `triage_at` empty is still unconfirmed. The stable reminder skips cases with no `stable_at` and I did not change that.

**Signal deduplication and snoozing**

- **Dedup windows (30 reported as 30 seconds):** `917a0b7b` changed the per-filter window to seconds, but the UI labels the field "Window (minutes)". I restored minutes in `src/dispatch/signal/service.py` and changed the column default in `models.py` to 60. Existing filters work without edits. Regression test: `test_filter_actions_deduplicate_window_is_in_minutes`.
- **Snoozes (expired filter blocks valid one):** `086dc910` changed an expired snooze filter from `continue` to `break`, so later filters on the same signal were never checked. I changed it back. Regression test: `test_filter_actions_snooze_skips_expired_filter`.
- **Canary signals:** `a348bbd2` (2025-05-29) excluded canary signals from dedup. I did not change this.

Test results: `python -m pytest tests/signal tests/case` gives 61 passed and 1 skipped. Two unrelated tests in `tests/ai` and `tests/database` already fail on the untouched code.

Nothing is committed. Open items: the schema default for `window` in `models.py` (600) is still a number of minutes, which is now 10 hours. Rows created before the change without an explicit window have 3600 stored, which now means 60 hours. Both need a decision.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
SNOOZE_BUG: 086dc910c308c8e5a91f5be8b4624cce11feae85
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES