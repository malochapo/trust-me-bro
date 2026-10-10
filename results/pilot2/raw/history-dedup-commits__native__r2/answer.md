Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All four edit `src/dispatch/signal/service.py`.

- **a348bbd2** (2025-05-29) stops canary signals from being deduplicated. `filter_dedup` now returns early for canary instances, and earlier canary instances are ignored when looking for duplicates.
- **7a9fe810** (2025-06-19) makes the default deduplication window configurable. It was hard-coded to 1 hour and now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- **086dc910** (2025-08-07) simplifies the snooze filter checks. Its diff also changes an expired snooze filter from `continue` to `break`, so the loop now stops at the first expired filter. That can change which filters get checked.
- **917a0b7b** (2025-08-14) adds a shared `_window_start` helper for the lookback window. It also changes `SignalFilter.window` from being read as minutes to being read as seconds, which changes the dedup window for filters.

I left out other commits that touch signal code (logging, redaction, stats, UI). They don't change the snooze or dedup decision.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b