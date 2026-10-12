## Recap

**Weekly reminders stopped after the 2025-08-13 deploy.** `_is_reminder_day()` compared `date.today().isoweekday()` (Monday = 1) with `calendar.MONDAY` (Monday = 0), so it was never true. This suppressed both the triage and stable weekly reminders. Daily triage reminders were unaffected because they don't use the helper.

**The fix** (`src/dispatch/case/scheduled.py`): the helper now uses `weekday()`, which matches `calendar.MONDAY`. Separately, `case_close_reminder` now counts from `created_at` when `triage_at` is missing.

**The evening TypeError** comes from subtracting a `NULL` `triage_at` from `utcnow()`. Triage can be entered without setting `triage_at`: the Slack triage and button handlers assign the status directly, and the edit-case submission runs the transition before the update, so the transition never fires. The logs don't identify which cases. The ordering bug is still there; I haven't fixed it.

**Tests** (`tests/case/test_case_scheduled.py`, new): 7 cases for the weekday check, one per day of the week, and 3 for the close reminder fallback. Both bug tests fail on the pre-fix code. `python -m pytest tests/case` passes (25 tests). Nothing is committed.

**Caveats:** the logs don't record reminder sends, so the missed Mondays come from the code and deploy times, not from send logs. `case_stable_reminder` still skips stable cases with no `stable_at`. I left that alone because you asked only for the close reminder.

FILE: src/dispatch/case/scheduled.py
FUNCTION: _is_reminder_day
INTRODUCED_BY: c509d45e97f4eeacf950450c142ee27da8fcda3f
DEPLOYED_IMAGE: registry.example.com/dispatch:main-81d8ae42
FIRST_MISSED: 2025-08-18
MISSING_FIELD: triage_at