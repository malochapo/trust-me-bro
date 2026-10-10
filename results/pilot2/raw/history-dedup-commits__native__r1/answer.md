Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All four are in `src/dispatch/signal/service.py`:

- **a348bbd2** (2025-05-29, "don't dedup on canary signals"): `filter_dedup` now returns early for canary instances. Canary instances are also excluded from the dedup lookups.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the default dedup window for signals with no filters was a hard-coded 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): titled a refactor, but one behaviour changed in `filter_snooze`. An expired snooze filter now hits `break` instead of `continue`, so the loop stops there and skips any filters after it. It also drops the warnings for filters with no mode or action; a missing mode or action is now silently skipped.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): titled a refactor, but it changes the units of the per-filter dedup window. A new `_window_start(seconds)` helper reads `SignalFilter.window` as seconds, where the old code read it as minutes. The default window still works out to the configured minutes.

I left out `5e136d7b` and `01c28ff0`. They change the UI that displays snoozes and triggers, not the decision logic. I also left out `dee1699d`, which only matched on keywords in the search.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b