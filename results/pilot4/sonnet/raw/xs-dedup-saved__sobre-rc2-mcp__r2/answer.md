The commit that broke it is `917a0b7b` (2025-08-14), labelled "refactor(signal): share the lookback window computation". The fix is in and the new regression test passes. The signal tests pass: 33 passed, 1 skipped.

**Cause:** the refactor changed the per-filter dedup lookback from `timedelta(minutes=f.window)` to `timedelta(seconds=f.window)`. The UI labels the field "Window (minutes)" and existing rows store minutes, so a window of 30 became 30 seconds. Two instances ten minutes apart then fell outside the window and opened separate cases.

**Fix:**
- **Window unit:** in `src/dispatch/signal/service.py`, `filter_dedup` now uses `_window_start(f.window * 60)`, so the window is in minutes again. Stored values are unchanged, so existing filters work without being edited and no migration is needed.
- **Defaults:** in `src/dispatch/signal/models.py` I also changed the defaults that had been written as seconds, because they would now mean 60 hours and 10 hours. The model default goes from 3600 to 60 and the schema default from 600 to 10. Both still mean 1 hour and 10 minutes.

**Regression test:** `test_filter_dedup_window_is_in_minutes` uses a filter with a 30-minute window and an earlier instance 10 minutes old that already has a case. It asserts the new instance is deduplicated into that case. With the source fix stashed, it fails.

**Canary:** `a348bbd2` (2025-05-29) made canary instances skip dedup and excluded earlier canary instances from dedup queries.

**Default window:** signals with no filter group instances within 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`. Commit `7a9fe810` introduced that setting. The `filter_signal` docstring still says 1 hour, which is out of date.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES