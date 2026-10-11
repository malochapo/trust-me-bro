**Recap**

Two regressions came from commits labelled as refactors, and both are now fixed in the working tree. Nothing is committed yet.

- **Deduplication windows.** `917a0b7b` changed the per-filter lookback from minutes to seconds. A filter window of 30, set in minutes in the UI, was applied as 30 seconds, so instances ten minutes apart opened separate cases. The window is now read as minutes again (`f.window * 60`). I also corrected the `SignalFilter.window` column comment and default (now 60 minutes). The regression test is `test_filter_actions_deduplicate_window_is_in_minutes`.
- **Snoozing.** `086dc910` turned `continue` into `break` for expired snooze filters. An expired snooze listed before a valid one stopped the loop, so the valid snooze was never applied. It is now `continue` again. The regression test is `test_filter_actions_snooze_expired_then_active`.
- **Canary signals.** `a348bbd2` made canary instances skip deduplication and excluded existing canary instances from the dedup queries.
- **Default window.** `7a9fe810` made the window for signals without a filter configurable. It was 1 hour and is now 45 minutes by default, and `917a0b7b` left it at 45 minutes. The `filter_signal` docstring still says "1-hour window" and is out of date.

`tests/signal/test_signal_service.py` gives 16 passed and 1 skipped.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES