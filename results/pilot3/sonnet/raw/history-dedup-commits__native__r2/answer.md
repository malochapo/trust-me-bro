Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. Each one changed `filter_snooze` or `filter_dedup` in `src/dispatch/signal/service.py`.

- **a348bbd2** (2025-05-29, "don't dedup on canary signals"): `filter_dedup` now returns early for canary instances. Canary instances are also excluded from the candidate instances it matches against.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the default window for signals with no filters was a hard-coded 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): it is labeled a refactor but changes behaviour. When `filter_snooze` hits an expired filter it now does `break` instead of `continue`, so later filters are no longer checked. The explicit no-mode and no-action warnings were also folded into one condition.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): it is also labeled a refactor but changes behaviour. A new `_window_start(seconds)` helper now computes the lookback for both the default window and per-filter windows. Per-filter windows (`SignalFilter.window`) used to be treated as minutes and are now treated as seconds. The default window is converted with `* 60`, so it stays in minutes.

I left out three other commits touching the signal code, because none changed the snooze or dedup decision or its time windows:
- 4474af25 only adds logging.
- d2675cf4 only redacts the raw payload.
- 5e136d7b is a UI change.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b