Four commits since 2025-05-22 changed how Dispatch decides whether a signal instance is snoozed or deduplicated. I read the diffs of the candidate commits and searched the history for others touching snooze, dedup or window logic.

- **a348bbd2** (2025-05-29, "don't dedup on canary signals"): canary instances now skip deduplication entirely, and canary instances are excluded from the dedup lookups.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the default dedup window was hard-coded at 1 hour. It is now read from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): the snooze filter loop was rewritten. A non-active or non-snooze filter now hits `break` instead of `continue`, which changes how the loop picks a snooze filter. I counted it despite the "refactor" label because of that change.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): `SignalFilter.window` is now treated as seconds, where before it was treated as minutes. That changes the snooze window length. The default dedup window computation was also moved into the new helper.

I excluded two commits that matched on keywords but don't change the decision:
- **4474af25** only adds log lines.
- **5e136d7b** only adds UI views for snoozes.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b