Four commits since 2025-05-22 changed how Dispatch decides whether a signal instance is snoozed or deduplicated, or the time windows it uses.

- **a348bbd2** (2025-05-29, fix): skips deduplication for canary signals and excludes canary instances from dedup matches.
- **7a9fe810** (2025-06-19, feat): makes the default dedup window configurable through `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes. It was previously hard-coded to 1 hour.
- **086dc910** (2025-08-07, refactor): labelled a refactor, but it changes snooze behaviour. An expired snooze filter now `break`s out of the loop instead of `continue`-ing, so later snooze filters are no longer checked.
- **917a0b7b** (2025-08-14, refactor): changes the custom filter dedup window. `SignalFilter.window` was treated as minutes and is now treated as seconds, so the window a filter gives is different from before.

I excluded commits that only change the UI or logging, such as 4474af25 (logs the outcome) and 90f73fe2 (relabels "filtered" as "snoozed"). I searched both commit messages and the full history for window, snooze, dedup and expiration changes, and checked the signal backend files directly.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b