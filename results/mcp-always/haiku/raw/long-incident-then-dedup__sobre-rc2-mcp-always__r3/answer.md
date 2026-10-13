**Weekly reminders (weekday bug):** Assignees stopped getting the Monday reminders to close long-running triage and stable cases. The check `_is_reminder_day` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true. The bug came in with `c509d45e` (2025-08-12, "share the weekly reminder check") and first shipped in `main-81d8ae42`, which started on the scheduler at 2025-08-13T16:40Z. The first Monday with no reminders was 2025-08-18. The fix uses `.weekday()`, and `tests/case/test_case_scheduled.py` covers each day of the week and the `calendar.MONDAY` comparison.

**Close reminder TypeError:** The job logged a TypeError every evening because `case.triage_at` was NULL for some cases in triage, and the code subtracted it from the current time. Cases can end up with no `triage_at` in two ways: the 2022 column was added without a backfill, and the Slack reopen button sets the status without running the transition flow that records it. I couldn't confirm which production rows are affected. The fix counts from `created_at` when `triage_at` is missing, and three tests cover that case, the recent-case case, and the case where `triage_at` takes precedence.

**Signal deduplication and snoozing:** Three commits since 2025-05-22 are involved:
- `917a0b7b` read the deduplication filter window as seconds instead of minutes, so a 30-minute window looked back 30 seconds. Fixed in `filter_dedup`, with a regression test that fails on the old code.
- `086dc910` changed an expired snooze from `continue` to `break`, so an expired snooze listed before an active one stopped the check and let the active snooze be skipped. Fixed, with a regression test that fails with `break`.
- `a348bbd2` changed canary signals so they are excluded from deduplication. This was a deliberate behaviour change, not a bug, and I left it as is.

Nothing is committed. The working tree has changes in `src/dispatch/case/scheduled.py`, `src/dispatch/signal/service.py`, `tests/signal/test_signal_service.py` and the new `tests/case/test_case_scheduled.py`. Last run: `python -m pytest tests/signal tests/case tests/case_cost` gives 80 passed, 1 skipped.

Open items: the reopen button still skips the transition flow, the stable reminder still skips cases with no `stable_at`, and the `triage_at` backfill hasn't been run. The column comment and Pydantic default for `SignalFilter.window` also still describe seconds, though the code now uses minutes; I didn't change those.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97
DEPLOYED_IMAGE: main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at
DEDUP_WINDOW_BUG: 917a0b7b0d
SNOOZE_BUG: 086dc910c3
CANARY: a348bbd267
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES