**Recap**

Two regressions came from refactors in August 2025, and both are now fixed in the working tree (nothing committed).

- **Dedup windows:** `917a0b7b` changed per-filter dedup to read `SignalFilter.window` as seconds. The UI stores minutes, so a window of 30 acted as 30 seconds and instances ten minutes apart opened separate cases. `_window_start` now takes minutes again, and the stale column comment is corrected. Regression test: `test_filter_actions_deduplicate_window_is_in_minutes`.
- **Snoozing:** `086dc910` turned the `continue` after an expired snooze filter into `break`, so one expired filter stopped the loop before a still-valid one was checked. It is `continue` again. Regression test: `test_filter_actions_snooze_expired_then_valid`.
- **Canary signals:** `a348bbd2` made `filter_dedup` return early for canary instances and excluded existing canary instances from both dedup queries. This was intended behavior and is unchanged.
- **Default window:** `7a9fe810` made the window for signals without filters configurable and changed it from 1 hour to 45 minutes. The `filter_signal` docstring still says 1 hour, which is stale.
- **Left alone:** the column default (`60 * 60`) and schema default (`600`) for `window` are now read as minutes, which looks odd. I did not change them.

`tests/signal` passes with 34 passed and 1 skipped. I did not run the rest of the suite.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES