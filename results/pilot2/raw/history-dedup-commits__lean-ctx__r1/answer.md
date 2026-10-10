Four commits since 2025-05-22 changed how `filter_snooze` or `filter_dedup` in `src/dispatch/signal/service.py` decides whether a new signal instance is snoozed or deduplicated:

- **a348bbd2** (2025-05-29, "don't dedup on canary signals"): canary signal instances now skip deduplication, and canary instances are excluded from the dedup lookups.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the default dedup window for signals with no filters was hard-coded at 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): this is mostly a refactor, but one line changed behaviour. An expired snooze filter used to `continue` to the next filter and now does `break`, so later filters are no longer checked.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): this is labelled a refactor, but it changes the time window. The per-filter dedup window `f.window` was read as minutes and is now read as seconds. The default window is converted from minutes to seconds so it stays the same.

I left out the other commits that mention snooze or dedup. The ones I looked at only touched UI labels, a model default, or logging and redaction, not the snooze/dedup decision.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b