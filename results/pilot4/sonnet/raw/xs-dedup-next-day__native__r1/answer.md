The commit that broke deduplication windows is `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14). The new regression test fails on the old code and passes with the fix. All of `tests/signal` passes: 33 passed, 1 skipped.

**Cause.** Before that commit, the filter's window was applied as `timedelta(minutes=f.window)`. The UI field is labelled "Window (minutes)", and existing rows hold minutes. The refactor added a helper that takes seconds and passed `f.window` straight into it, with a comment saying the window is stored in seconds. A window of 30 therefore became 30 seconds, so two instances ten minutes apart no longer deduplicated.

**Fix.**
- `src/dispatch/signal/service.py`: the filter window is now converted with `(f.window or 0) * 60`. Existing filters work without being edited, since no stored data changes.
- `src/dispatch/signal/models.py`: I corrected the misleading "seconds" comment on the column. I also changed the column default from `3600` to `60`, so a new filter created without a window gets one hour rather than 3600 minutes. That default only affects new rows.

**Test.** `test_filter_actions_deduplicate_window_is_in_minutes` uses a window of 30 and an instance from 10 minutes earlier. The second instance must join the first one's case.

Existing tests that attach a filter with `signal.filters.append(SignalFilterFactory(...))` never actually attach it, so `signal.filters` is empty when `filter_dedup` runs. They end up exercising the default window instead. The new test calls `session.add` on the filter first. I left the old tests alone.

The default window for signals with no filter is 45 minutes (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, made configurable in `7a9fe810`). The `filter_signal` docstring still says "1-hour window", which is stale. I didn't change it.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES