The commit that broke deduplication windows is `917a0b7b` (2025-08-14, "share the lookback window computation"). I fixed it, added two regression tests, and all of `tests/signal` passes (34 passed, 1 skipped).

**Cause.** That commit added `_window_start(seconds)` and changed the filter path from `timedelta(minutes=f.window)` to `_window_start(f.window)`. It also added a comment, "SignalFilter.window is stored in seconds", which is wrong. The UI offers "Window (minutes)" with 5, 10, 15, 20 and 30, so stored values are minutes. After the commit, a window of 30 was treated as 30 seconds, so two instances ten minutes apart never grouped. The model's column comment already said "seconds", but the stored data and the UI both use minutes.

**Fix.**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The filter path passes `f.window` unchanged, so existing filters work without edits. The default no-filter path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` directly, with no `* 60`.
- `src/dispatch/signal/models.py`: the column's Python-side default is now 60 with a "minutes" comment. It was 3600, which would have meant 60 hours once read as minutes. This only affects new filters created without an explicit window.

**Tests** (in `tests/signal/test_signal_service.py`):
- `test_filter_actions_deduplicate_window_is_in_minutes`: with window=30, an instance 10 minutes old is deduplicated. With the fix stashed, this one fails.
- `test_filter_actions_deduplicate_outside_window`: with window=30, an instance 40 minutes old is not deduplicated. It passes with or without the fix, so it only guards against the window being too wide.

I had no record of yesterday's list, so I re-derived the commits from `git log` since 2025-05-22.

**The other two answers:**
- **Canary:** `a348bbd2` (2025-05-29, "don't dedup on canary signals").
- **Default window:** signals without a filter group for 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. It became configurable in `7a9fe810`.
- **Stale docstring:** the `filter_signal` docstring still says "1-hour window". I didn't change it.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES