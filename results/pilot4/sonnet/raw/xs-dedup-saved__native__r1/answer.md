The breaking commit is `917a0b7b` (2025-08-14, "share the lookback window computation"). The signal tests pass with the fix (33 passed, 1 skipped). The new regression test fails without it.

**Cause:** `SignalFilter.window` holds minutes. The UI field is labelled "Window (minutes)", with choices 5, 10, 15, 20 and 30. Before `917a0b7b` the code used `timedelta(minutes=f.window)`. That commit switched it to seconds, so a window of 30 became 30 seconds. Instances ten minutes apart then fell outside the window and each opened its own case.

My notes from yesterday said that commit "fixed a unit bug" because the column is in seconds. That was wrong: the model comment saying "seconds" was misleading, and the UI and stored data are in minutes.

**Fix:**
- In `src/dispatch/signal/service.py`, the filter window is now `_window_start(f.window * 60)`. Existing filters work as stored, with no edits or migration.
- In `src/dispatch/signal/service.py`, I also corrected the stale "1-hour window" wording in the `filter_signal` docstring to 45 minutes.
- In `src/dispatch/signal/models.py`, I fixed the column comment to say minutes. I also changed the Python-side default from `60 * 60` to `60`, so a new filter defaults to 60 minutes rather than 60 hours. Existing rows are not touched.

**Test:** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It uses a 30-minute window. An instance 10 minutes old is deduplicated, and one 45 minutes old is not.

The canary commit is `a348bbd2` (#6026), which makes canary signals skip deduplication. The default window for signals without a filter is 45 minutes. `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py` changes it.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES