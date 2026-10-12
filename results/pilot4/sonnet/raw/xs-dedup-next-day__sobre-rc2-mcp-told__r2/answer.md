Commit `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14) caused the bug. I fixed it and added a regression test. The signal tests pass, 15 passed and 1 skipped. The new test fails without the fix.

**Cause:** The commit assumed `SignalFilter.window` was stored in seconds. It changed `timedelta(minutes=f.window)` to `timedelta(seconds=f.window)`. The UI field is labelled "Window (minutes)" and the stored values are minutes, so a window of 30 became 30 seconds. Two instances ten minutes apart no longer matched, and each opened its own case.

**Fix:**
- **Window unit:** `_window_start` in `src/dispatch/signal/service.py` now takes minutes. The default-window call no longer multiplies by 60. Stored values were always minutes, so existing filters work without any edit or migration.
- **Stale text:** I corrected the misleading "seconds" comment on the model column and the "1-hour" text in the `filter_signal` docstring.
- **Regression test:** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It sets a window of 30 with an earlier instance 10 minutes old, and checks the new instance is deduplicated into the existing case.

**One more problem I did not fix:** `086dc910` ("simplify snooze filter checks") changed `continue` to `break` for expired snooze filters in `filter_snooze`. An expired filter now stops the loop, so any snooze filters after it are skipped. You'll probably want to look at that.

The canary commit is `a348bbd2`. It makes `filter_dedup` return early for canary instances and excludes canary instances from the matching queries. The default window was first made configurable in `7a9fe810`.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES