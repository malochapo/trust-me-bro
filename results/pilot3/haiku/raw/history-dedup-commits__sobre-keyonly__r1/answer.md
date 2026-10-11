Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated, including the time windows. All four touch `src/dispatch/signal/service.py`:

- **`a348bbd2`** (2025-05-29, "fix(signal): don't dedup on canary signals"): canary signals skip deduplication, both in the early return and in the dedup query.
- **`7a9fe810`** (2025-06-19, "make the default deduplication window configurable"): the default dedup lookback moved from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
- **`086dc910`** (2025-08-07, "simplify snooze filter checks"): snooze filters are skipped unless their mode is active and their action is snooze. An expired filter now `break`s the loop instead of `continue`-ing, so later filters are no longer checked once one has expired. The warning logs for missing mode and action were also removed.
- **`917a0b7b`** (2025-08-14, "share the lookback window computation"): a helper now computes the window start, and snooze filter windows are read as seconds rather than minutes.

I excluded `5e136d7b`, which only adds UI views for snoozes, and the other signal commits (logging, redaction), which don't touch snooze or dedup decisions or their windows.

COMMITS: 917a0b7b, 086dc910, 7a9fe810, a348bbd2