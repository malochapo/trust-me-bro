The commit that broke it is `917a0b7b`, "refactor(signal): share the lookback window computation" (2025-08-14). The fix is in and the signal tests pass.

**Cause:** the refactor changed the per-filter lookback from `timedelta(minutes=f.window)` to seconds. It assumed the column held seconds, going by a misleading comment on `SignalFilter.window`. The UI offers "Window (minutes)" and saves minutes, so a window of 30 became 30 seconds. Two instances ten minutes apart were therefore never grouped.

**Correction to my earlier summary:** I said yesterday that `917a0b7b` made the window seconds, as if that were intended. That was wrong. The stored values are minutes, and the commit introduced the bug.

**Fix:**
- `src/dispatch/signal/service.py`: the filter window is now `_window_start(f.window * 60)`, so it is read as minutes again. Existing filters keep working with no data migration. I also corrected the stale "1-hour" default in the `filter_signal` docstring.
- `src/dispatch/signal/models.py`: the column comment now says minutes.
- `tests/signal/test_signal_service.py`: new `test_filter_actions_deduplicate_window_is_minutes`. It uses a window of 30 and an earlier instance ten minutes old, and expects the new instance to join its case. It fails without the fix.

One thing I left alone: the DB column default of 3600 and the pydantic default of 600 are now read as minutes, which is much longer than they look. Changing them would alter behaviour for existing rows, so say if you want that handled separately.

The canary commit is `a348bbd2`. It makes `filter_dedup` return early for canary instances and excludes canary instances from the dedup queries. The default window comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 (set in `src/dispatch/config.py`).

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES