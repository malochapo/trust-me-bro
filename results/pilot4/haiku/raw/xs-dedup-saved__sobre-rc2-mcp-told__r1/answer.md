The deduplication window bug was caused by `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14). It is not a behaviour-preserving refactor. Before it, `filter_dedup` subtracted `f.window` as minutes. After it, the value is passed as seconds, so a window of 30 looks back 30 seconds. The UI offers 5–30 labelled "minutes" and sends them unconverted, so the 10-minute pair fell outside the window and opened two cases.

**Fix**
- `src/dispatch/signal/service.py`: `filter_dedup` now uses `_window_start(f.window * 60)`, so a filter's window is in minutes, as the UI says. Existing filters need no edits, since their stored numbers already meant minutes.
- `src/dispatch/signal/service.py`: the `filter_signal` docstring now gives the default window as 45 minutes instead of the stale "1-hour".
- `src/dispatch/signal/models.py`: the `SignalFilter.window` column default is now 60 (minutes), and the API schema default is now 10 (minutes). The old values, 3600 and 600, would have meant 60 hours and 10 hours under the minutes unit.
- `tests/signal/test_signal_service.py`: new `test_filter_actions_deduplicate_window_is_minutes`. It creates an instance 10 minutes earlier and a window of 30, then expects deduplication. It fails on the original code and passes with the fix.

**Tests:** `tests/signal` passes (15 passed, 1 skipped), and `tests/signal` plus `tests/case` passes (48 passed, 1 skipped), run with `python -m pytest`.

**Caveat:** any filter created through the API after `917a0b7b` with a seconds-sized value, such as 600 or 3600, will now look back that many minutes. I could not tell those apart from UI-created filters, so check for them if any exist.

I did not change the UI, since it already labels and sends minutes. The `break` change in `086dc910` is a separate behaviour change, and I left it alone. The memory file's open issue about the minutes/seconds mismatch is now resolved in code, but I did not update the memory file.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES