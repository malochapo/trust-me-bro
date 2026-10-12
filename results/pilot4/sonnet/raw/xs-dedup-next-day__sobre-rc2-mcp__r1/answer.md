The regression test fails on the old code and passes with the fix. The signal tests pass, with 33 passed and 1 skipped.

**Cause:** commit `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14). Before it, `filter_dedup` used `timedelta(minutes=f.window)`. The refactor added a `_window_start(seconds)` helper and passed it `f.window`, with a comment saying the window is stored in seconds. The window is stored in minutes, so a window of 30 became 30 seconds. Two instances ten minutes apart fell outside it and each opened a case.

Of the commits I found, the others don't touch the window:
- `a348bbd2` is the canary change.
- `7a9fe810` made the default window configurable.
- `086dc910` only simplified the snooze checks.

**Fix:**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The default-window call no longer multiplies by 60.
- `src/dispatch/signal/models.py`: corrected the misleading "seconds" comment on `SignalFilter.window`.
- Existing filters need no editing, because the stored values were always minutes.
- `tests/signal/test_signal_service.py`: new `test_filter_dedup_window_is_in_minutes`. It uses a window of 30 and an instance from 10 minutes earlier.

**Defaults I left alone:** the column default is `60 * 60` and the pydantic default is `600`. Both are now read as minutes, which is probably not what was intended. I left them because changing them would alter new filters.

**Test gotcha:** `signal.filters.append(SignalFilterFactory(...))` silently attaches nothing, because the factory commits while the collection is being evaluated. Existing tests that use this pattern may be passing through the default window without exercising their filter. I didn't check or change them.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES