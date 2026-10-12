The commit that broke deduplication windows is **917a0b7b** (2025-08-14, "refactor(signal): share the lookback window computation"). It replaced `timedelta(minutes=f.window)` with a seconds-based helper, so a filter window of 30 became 30 seconds. Your two instances ten minutes apart fell outside that window and opened two cases.

**The fix**
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again, and both the filter window and the default window use minutes. The `filter_signal` docstring no longer claims a fixed 1-hour default.
- `src/dispatch/signal/models.py`: the `SignalFilter.window` column default is 60 minutes (was 3600 "seconds"), and the schema default is 10 minutes (was 600). This is the same effective behaviour as before the bug, just in the correct unit.
- No migration: stored filters already hold minute values (for example 30 from the UI), so they start working as intended without being edited.

**Regression test**
- `tests/signal/test_signal_service.py::test_filter_actions_deduplicate_window_is_minutes` uses a 30-minute deduplicate filter. An instance 10 minutes old groups with the new one; one 40 minutes old does not. The 10-minute case failed on the old code and passes now.
- `python -m pytest tests/signal` gives 34 passed, 1 skipped. The skip was already there.

**Other things I checked**
- The canary commit is **a348bbd2**. It made `filter_dedup` return early for canary instances and excluded canary instances from dedup queries. The current code still does this.
- Commit 086dc910 changed `continue` to `break` in snooze handling. That affects snooze, not window units, so it is not the cause here.
- The UI dialog (`SignalFilterCreateDialog.vue`) already labels the window in minutes, so no UI change was needed.
- I did not commit. The changes are in the working tree.
- Black reports a pre-existing formatting issue at `models.py:411`, which I left alone.

I also updated the memory note on this history, since it said windows were seconds.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES