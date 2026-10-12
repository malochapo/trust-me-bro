Deduplication windows are fixed. The filter's `window` is read as minutes again, which is what the UI shows, so existing filters work without edits.

**Cause:** commit `917a0b7b`, "refactor(signal): share the lookback window computation" from 2025-08-14. It changed the per-filter lookback from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which reads the value as seconds. A window of 30 became 30 seconds, so two instances ten minutes apart no longer deduplicated. The existing stored values were entered in minutes, so no data migration is needed.

**Changes:**
- `src/dispatch/signal/service.py`: the filter window is now `_window_start(f.window * 60)`. I also corrected the stale "1-hour window" text in the `filter_signal` docstring.
- `src/dispatch/signal/models.py`: the column default is now 60, and the schema default is now 10. Both are in minutes, the same durations as before (1 hour and 10 minutes), but in the unit the code now reads.
- `tests/signal/test_signal_service.py`: new `test_filter_actions_deduplicate_window_is_minutes`. A 10-minute-old instance must deduplicate into a 30-minute-window filter's case. It fails on the old code and passes on the new.

All of `tests/signal` passes: 33 passed, 1 skipped.

The existing dedup tests didn't catch this. In the one I debugged, the filter never actually attached to the signal, so it exercised only the default 45-minute window. The other tests that use the same filter setup may have the same problem; I didn't check them.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES