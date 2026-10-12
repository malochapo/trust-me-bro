Here is the recap for both investigations. Nothing is committed yet. All changes are in the working tree.

**Weekly reminders (weekday bug)**

Commit `c509d45e` (2025-08-12, "refactor(case): share the weekly reminder check") moved the Monday check into `_is_reminder_day()`. The new check compared `date.today().isoweekday()` with `calendar.MONDAY`. `isoweekday()` returns 1 for Monday, while `calendar.MONDAY` is 0, so the check was never true. Weekly close and stable reminders stopped. Daily triage reminders don't use this check, so they kept working. The commit was in the image deployed on 2025-08-13 16:40 UTC (`main-81d8ae42`, web and scheduler). The first Monday without reminders was 2025-08-18.

Fix: `_is_reminder_day()` uses `date.today().weekday() == calendar.MONDAY`. Regression test: `tests/case/test_case_scheduled.py::test_is_reminder_day`, parametrized over a Monday and each other day of the week.

**Evening TypeError (case close reminder)**

`case_close_reminder` subtracts `case.triage_at` from the current time. Some cases in `triage` have no `triage_at`, so the subtraction raises a TypeError every evening. `triage_at` is only set when the triage flow runs. The Slack reopen button sets the status without running it, and legacy rows from the 2022 migration were never backfilled. The logs have no case IDs, so I haven't confirmed which path produced the rows in your database.

Fix: the job counts from `triage_at or created_at`, so those cases get their weekly reminder. Tests cover a missing `triage_at` with an old case (reminder sent), a recent case (no reminder), and a `triage_at` that takes precedence over `created_at`.

**Deduplication windows (window units)**

Commit `917a0b7b` (2025-08-14, "share the lookback window computation") changed `SignalFilter.window` from minutes to seconds. The UI labels the field "Window (minutes)", so a window of 30 was effectively 30 seconds. Two instances ten minutes apart opened two cases. Fix: the window is read as minutes again, the column default is 60 minutes, and the default-window path passes minutes. Existing filters work without edits. Regression test: `test_filter_actions_deduplicate_window_is_in_minutes`.

**Snoozing (expired filter stops the check)**

Commit `086dc910` (2025-08-07, "simplify snooze filter checks") changed the expired-filter branch in `filter_snooze` from `continue` to `break`. An expired snooze filter now stopped the loop, so a valid filter listed after it never ran. Fix: restored `continue`. Regression test: `test_filter_actions_snooze_skips_expired_filter`, with the expired filter listed first.

**Canary signals**

Commit `a348bbd2` (2025-05-29, "don't dedup on canary signals") is the commit that changed canary deduplication. It skips dedup for canary instances and excludes them from matching.

**Test status**

`python -m pytest` runs 371 passed, 4 skipped, 8 failed. The 8 failures are in `tests/ai/test_ai_service.py` (6), `tests/database/test_service.py::test_restricted_case_filter_with_test_data`, and `tests/entity/test_entity_service.py::test_find_entities_with_field_only`. They fail the same way on a clean checkout of HEAD, so they predate these changes. I did not investigate them.

**Open items**

- The `triage_at` cause is not confirmed against your database. Run `SELECT id, created_at FROM "case" WHERE status = 'triage' AND triage_at IS NULL;` in each tenant schema to see which path produced the rows.
- The `case_stable_reminder` job still skips cases with no `stable_at`. I did not change that.
- The `SignalFilterBase.window` default is still 600, which is now 600 minutes (10 hours), as it was before `917a0b7b`.
- The `filter_signal` docstring still says "1-hour window". The default is 45 minutes.

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