The commit that broke deduplication windows is `917a0b7b`, "refactor(signal): share the lookback window computation" (2025-08-14). The new test fails on the old code and passes with the fix, and the rest of `tests/signal/test_signal_service.py` still passes.

**Cause.** Before that commit, `filter_dedup` computed the lookback as `timedelta(minutes=f.window)`. The commit moved this into `_window_start(seconds)` and switched it to `timedelta(seconds=...)`. It also added a comment saying the window is "stored in seconds". The filter dialog in the UI (`SignalFilterCreateDialog.vue`) offers the values 5, 10, 15, 20 and 30, labelled "Window (minutes)". So a window of 30 was read as 30 seconds, and two instances ten minutes apart no longer matched.

**Other commits I looked at:**
- `086dc910`: changes the snooze check, not dedup windows. It also swapped `continue` for `break` on an expired snooze filter. I left that alone.
- `7a9fe810`: made the default window configurable.
- `a348bbd2`: stopped deduplicating canary signals.

**Fix.**
- **`src/dispatch/signal/service.py`:** `_window_start` takes minutes again, and the default-window call no longer multiplies by 60. Stored values are already minutes, so existing filters work without editing.
- **`src/dispatch/signal/models.py`:** the `SignalFilter.window` column default was `3600` with a "seconds" comment. It is now `60` with a "minutes" comment, so an unset window means one hour. The schema default went from `600` to `10`. These two defaults would have been read as 3600 and 600 minutes under the corrected code.
- **Regression test:** `test_filter_actions_deduplicate_window_is_in_minutes` uses a filter with `window=30` and an instance created ten minutes earlier. It asserts the new instance is deduplicated.

While writing the test I found that the existing dedup tests do the same `signal.filters.append(SignalFilterFactory(...))` in one expression. In my test that left the signal with no filters, so the default window applied and the test passed on the broken code. Creating the filter first and appending it afterwards works, and my test does that and asserts `signal.filters` is non-empty. I did not touch the existing tests, but they may not be exercising their filters.

The `filter_signal` docstring still says the default window is 1 hour, but the actual default is 45 minutes.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES