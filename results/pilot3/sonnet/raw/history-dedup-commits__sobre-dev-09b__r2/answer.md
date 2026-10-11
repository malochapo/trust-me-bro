Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All four touch `src/dispatch/signal/service.py`.

- **a348bbd2** (2025-05-29, fix: don't dedup on canary signals) makes `filter_dedup` return early for canary instances. Canary instances are also excluded from the dedup queries.
- **7a9fe810** (2025-06-19, make the default dedup window configurable) replaces the hard-coded 1-hour default window with `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- **086dc910** (2025-08-07, "simplify snooze filter checks") is labelled a refactor, but it changes behaviour. An expired snooze filter now hits `break` instead of `continue`, so the remaining filters are no longer checked. It also drops the warnings and skips for filters with no mode or action.
- **917a0b7b** (2025-08-14, "share the lookback window computation") is also labelled a refactor but changes the time window. A signal filter's `window` was previously read as minutes and is now read as seconds, via the new `_window_start` helper. The default window is converted from minutes to seconds, so it is unchanged.

I left out these nearby commits because they don't change the snooze or dedup decision:

- **4474af25** only adds logging.
- **d2675cf4** only masks sensitive fields.
- The others that touched signal code are UI or stats work.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b