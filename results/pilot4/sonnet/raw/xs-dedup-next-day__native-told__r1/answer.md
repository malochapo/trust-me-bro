The commit that broke it is `917a0b7b` ("refactor(signal): share the lookback window computation"). It's fixed, and the new regression test fails on the old code and passes on the fix.

**Cause:** that refactor added `_window_start(seconds)`. It passed `f.window` to it as seconds. `SignalFilter.window` is stored in minutes. The UI dialog is labelled "Window (minutes)" and offers 5/10/15/20/30. A filter set to 30 therefore looked back only 30 seconds, so the 10-minute-old instance never matched and a second case was opened. The refactor also changed the default-window path to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, which is equivalent. The wrong `# stored in seconds` comment came from the same commit.

**Fix (`src/dispatch/signal/service.py`):**
- `_window_start` now takes minutes.
- Existing filters work unedited, because their stored values were always minutes.
- I corrected the stale comment and the `filter_signal` docstring, which said "1-hour" for the default.

**Test:** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It uses a filter with `window=30` and an instance 10 minutes old, and expects the new instance to be deduplicated into the same case. The whole `tests/signal` suite passes (33 passed, 1 skipped).

**Left alone:** the `SignalFilter.window` model default (`60 * 60`, commented as seconds) and the schema default (`600`) still read as seconds. If that were corrected to minutes it would change what new filters default to, so I didn't touch it. Say if you want it changed.

I haven't saved anything to memory and haven't committed.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES