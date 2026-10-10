Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated:

- **a348bbd2** (2025-05-29, "don't dedup on canary signals"): `filter_dedup` now skips deduplication for canary instances. Canary instances are also excluded from the dedup lookup queries.
- **7a9fe810** (2025-06-19): the default dedup window was a hard-coded 1 hour. It is now set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
- **086dc910** (2025-08-07, labelled a refactor): this simplified the snooze filter checks, but it also changed behavior. An expired snooze filter now hits `break` instead of `continue`, so the loop stops there instead of checking the remaining filters.
- **917a0b7b** (2025-08-14, labelled a refactor): this added a shared `_window_start(seconds)` helper. It also changed how per-filter windows are read. `SignalFilter.window` was used as minutes and is now treated as seconds, which changes the dedup window length.

I left out these commits, which touch signal code but not the snooze or dedup decision:

- **4474af25** only adds logging of each processed instance's outcome.
- **d2675cf4** only masks sensitive raw fields before processing.
- **50cf8979** and **90f73fe2** only change signal stats display and retrieval.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b