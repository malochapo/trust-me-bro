Four commits since 2025-05-22 changed how Dispatch decides whether a signal instance is snoozed or deduplicated, or changed the time windows involved. All four touch `src/dispatch/signal/service.py`:

- **a348bbd2** (2025-05-29, "fix(signal): don't dedup on canary signals"): canary instances skip deduplication, and canary instances are excluded from the candidates that dedup compares against.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the default dedup window for signals with no dedup filter moved from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): the expiry check in `filter_snooze` changed from `continue` to `break`, so an expired snooze filter now stops the loop instead of letting later filters be checked. The other changes in that commit (dropping the warnings for missing mode/action) don't alter the outcome.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): per-filter dedup windows were previously computed as `f.window` minutes and are now computed as `f.window` seconds, via a new `_window_start` helper. The code comment says `SignalFilter.window` is stored in seconds, but I did not check the schema or migrations to confirm the unit. If the stored values were minutes, this commit silently shortened every per-filter dedup window by a factor of 60.

I excluded commits that only touched the UI or other features that happened to contain the word "window" (e.g. d34d3725, e56c02f7, 9e3313c9).

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b