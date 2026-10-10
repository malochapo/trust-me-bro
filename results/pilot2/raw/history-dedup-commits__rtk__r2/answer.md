Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All four touch `src/dispatch/signal/service.py`, in `filter_snooze` or `filter_dedup`.

- **a348bbd2** (2025-05-29, "don't dedup on canary signals"): `filter_dedup` now returns early for canary signals. Canary instances are also excluded when it looks for earlier instances to dedup against.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the default dedup window was a hard-coded 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): this is mostly a cleanup, but it changes one behaviour in `filter_snooze`. An expired snooze filter now ends the loop with `break` instead of skipping to the next filter with `continue`. It also drops the warnings for filters with no mode or no action.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): adds a `_window_start(seconds)` helper. The default dedup window is passed as minutes × 60. A signal filter's own `f.window` was previously treated as minutes and is now treated as seconds, which changes the dedup window for filters that set one.

I left out other signal commits in the same period (log outcome, mask sensitive fields, stats, UI, tags). They don't touch the snooze or dedup decision.

COMMITS: a348bbd26723, 7a9fe8103c31, 086dc910c308, 917a0b7b0d2d