Commit `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14) caused it. The fix is in and tested.

**Cause:** the new `_window_start` helper treats its argument as seconds. The filter path passed it `f.window`, which the UI stores in minutes (the field is labelled "Window (minutes)" and offers 5–30). A window of 30 therefore became 30 seconds, so two instances ten minutes apart opened two cases. The commit also added a comment claiming the column was in seconds, which is wrong. The old `timedelta(minutes=f.window)` code was correct.

**Fix:**
- `_window_start` in `src/dispatch/signal/service.py` now takes minutes. Existing filters work unedited, because the stored values were always minutes.
- The no-filter path now passes the minutes setting directly instead of multiplying by 60.
- I corrected the misleading unit comments in `src/dispatch/signal/models.py`. The column default of 3600 and the schema default of 600 were also wrong for minutes, so both are now 60 (one hour). This only affects filters created without a window.

**Test:** `test_filter_dedup_window_is_in_minutes` in `tests/signal/test_signal_service.py` uses a 30-minute filter and an earlier instance from 10 minutes before. It fails on the old code and passes now. All of `tests/signal` passes: 33 passed, 1 skipped.

My first draft of the test passed on the old code too. The filter wasn't attached to the signal, so the no-filter path was doing the dedup. I fixed that by adding the filter to the session before appending it.

The canary commit is `a348bbd2`. It makes canary instances skip deduplication and excludes them from the instances other signals dedup against.

The default window for signals without a filter is 45 minutes. It was a hard-coded hour until `7a9fe810` made it configurable through `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES