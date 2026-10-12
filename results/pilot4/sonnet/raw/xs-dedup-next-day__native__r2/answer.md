Commit `917a0b7b` ("share the lookback window computation", 2025-08-14) broke it. The fix is in and the signal service tests pass.

**Cause:** `SignalFilter.window` holds minutes. The UI field is labelled "Window (minutes)", and the old code used `timedelta(minutes=f.window)`. The refactor added `_window_start(seconds)` and passed `f.window` straight in, with a comment saying the value is stored in seconds. A window of 30 therefore became 30 seconds, so two instances ten minutes apart opened two cases. No data is wrong, so existing filters work unchanged.

**Fix:** `filter_dedup` in `src/dispatch/signal/service.py` now calls `_window_start(f.window * 60)`, and the comment says minutes.

**Test:** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py` uses a window of 30 and an instance with a case from 10 minutes earlier. The new instance must be deduplicated into that case. It fails without the fix and passes with it.

Other things I noticed and left alone:
- The comment on `SignalFilter.window` in `signal/models.py` still says "seconds", and its default of `60 * 60` is wrong if the column is in minutes. The pydantic default of 600 has the same problem.
- Commit `086dc910` changed `continue` to `break` for an expired snooze filter in `filter_snooze`. An expired snooze now stops the check for any later snooze filters, which looks like a separate bug.
- The `filter_signal` docstring still says the default window is 1 hour. Commit `7a9fe810` made it configurable with a default of 45 minutes.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES