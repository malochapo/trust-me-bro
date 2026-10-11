**Recap**

- **Dedup windows:** commit `917a0b7b` made the per-filter window count seconds instead of minutes. The UI stores minutes, so a window of 30 acted as 30 seconds. `filter_dedup` in `service.py` now multiplies the window by 60 again. The column and schema defaults were corrected to minutes (60 and 10). I added a regression test, which fails without the fix and passes with it.
- **Snoozing:** commit `086dc910` changed `continue` to `break` for expired snooze filters. An expired filter listed ahead of a valid one stopped the loop, so the valid snooze never applied. It is back to `continue`, with a regression test.
- **Canary signals:** commit `a348bbd2` made canary instances skip deduplication and excluded them from the dedup lookups. I did not change this.
- **Default window:** signals without any filter group instances for 45 minutes. Commit `7a9fe810` made this configurable, and `917a0b7b` only rewrote how it is computed.
- **Status:** the fixes and tests are uncommitted. All of `tests/signal` passes (34 passed, 1 skipped).

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES