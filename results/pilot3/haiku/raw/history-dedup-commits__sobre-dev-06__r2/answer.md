Four commits changed how Dispatch decides whether a signal instance is snoozed or deduplicated, or the windows it uses. They are listed oldest first:

- **a348bbd2** (2025-05-29), `fix(signal): don't dedup on canary signals`: canary instances skip deduplication entirely, and are excluded from the lookup of prior instances.
- **7a9fe810** (2025-06-19), `feat(signal): make the default deduplication window configurable`: the default dedup window changes from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45.
- **086dc910** (2025-08-07), `refactor(signal): simplify snooze filter checks`: this is labelled a refactor, but it changes behaviour. When a snooze filter has expired, the loop now `break`s instead of `continue`-ing, so later filters are no longer checked.
- **917a0b7b** (2025-08-14), `refactor(signal): share the lookback window computation`: also labelled a refactor, but it changes the unit for snooze filter windows. `SignalFilter.window` was treated as minutes and is now treated as seconds.

I excluded commits that touch signal code without changing these decisions, including dee1699d, 4474af25, 5e136d7b, 01c28ff0, 90f73fe2, 200cd428, and d2675cf4. The masking commit d2675cf4 redacts `raw` before entity extraction, but it doesn't change the snooze or dedup logic or its windows.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b