Commit 917a0b7b ("share the lookback window computation") caused the bug. It added `_window_start(seconds)` and passed `f.window` into it, with a comment saying `SignalFilter.window` is stored in seconds. The UI's filter dialog labels the field "Window (minutes)", and the old code used `timedelta(minutes=f.window)`. After the commit, a window of 30 meant 30 seconds, so two instances ten minutes apart no longer deduplicated.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes, and filters pass `f.window` straight through. The default no-filter window also passes minutes, without the `* 60`. Stored values were already minutes, so existing filters work without being edited.
- `src/dispatch/signal/models.py`: I fixed the column and schema defaults, which were written in seconds (3600 and 600). They are now 60 and 10 minutes. The schema default is the one a filter created through the API without a window would get; at 600 it would have meant 10 hours.

**Regression test**
- `test_filter_dedup_window_is_in_minutes` has a 30-minute window and an instance 10 minutes old, and expects the new instance to join its case.
- It fails on the old code and passes with the fix.
- `tests/signal` passes: 33 passed, 1 skipped.

The `NN` in the default window below is from `7a9fe810`, which made the default window configurable. The canary commit is `a348bbd2`.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES