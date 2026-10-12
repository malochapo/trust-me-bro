The window bug came from `917a0b7b` (refactor, 2025-08-14). It is fixed, and a regression test covers it.

**Cause:** Before `917a0b7b`, `filter_dedup` computed the lookback as `timedelta(minutes=f.window)`, which matches the UI's "Window (minutes)" field (options 5–30). That commit replaced it with the shared `_window_start(f.window)` helper, which takes seconds, and added a comment saying the window is stored in seconds. Every existing filter's window therefore shrank 60×. A 30-minute filter became 30 seconds, so two instances ten minutes apart no longer grouped.

**Fix:**
- `src/dispatch/signal/service.py`: the filter path now calls `_window_start(f.window * 60)`, and the comment says the value is stored in minutes. No data migration is needed, so existing filters work unedited.
- `src/dispatch/signal/models.py`: corrected the comment to minutes and changed the column default from `60 * 60` to `60`, so the default still means one hour.
- `tests/signal/test_signal_service.py`: added `test_filter_actions_deduplicate_window_is_in_minutes`. It creates an earlier instance with a case, ten minutes old, and a deduplicate filter with `window=30`, then asserts the new instance joins that case. I confirmed it fails with the buggy line restored and passes with the fix.

**Tests:** `python -m pytest tests/signal` gives 33 passed, 1 skipped against PostgreSQL.

**Things I did not change:**
- The Pydantic `SignalFilterBase.window` default is still `600`, which under the minutes unit is 10 hours. It only applies when the API omits the field, so I left it alone; say if you want it changed to 60.
- The `ruff format --check` complaint on `models.py` existed before my change.
- The 2025-05-22 commit list was not in my context, so I rebuilt it from `git log`. The dedup/snooze-related commits were `a348bbd2`, `7a9fe810`, `086dc910`, and `917a0b7b`. Only `917a0b7b` touches the window arithmetic.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES