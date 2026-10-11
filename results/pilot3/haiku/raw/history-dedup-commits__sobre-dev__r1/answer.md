Four commits changed how Dispatch decides whether a signal instance is snoozed or deduplicated, or the windows it uses:

- **a348bbd2** (2025-05-29), *fix(signal): don't dedup on canary signals*: canary instances skip deduplication, both as the candidate and as matches.
- **7a9fe810** (2025-06-19), *make the default deduplication window configurable*: the default dedup window was a hard-coded 1 hour; it now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45.
- **086dc910** (2025-08-07), *simplify snooze filter checks*: besides the cleanup, an expired snooze filter now `break`s out of the loop instead of `continue`, so later snooze filters on the signal are no longer evaluated.
- **917a0b7b** (2025-08-14), *share the lookback window computation*: the per-filter window is now treated as seconds (`_window_start(f.window)`), where it was previously minutes. This is a units change, not just a refactor, so it affects existing filters.

I excluded commits that touch the same area without changing the decision or its windows:
- **d2675cf4** masks raw fields before entity extraction.
- **4474af25** only adds log lines.
- **5e136d7b**, **90f73fe2**, and **01c28ff0** are UI or schema changes that mention snooze.
- **dee1699d** is an unrelated project and reporting change.

I did not run the test suite. The conclusions come from reading the diffs and the history of `src/dispatch/signal/`.

COMMITS: 086dc910, 917a0b7b, 7a9fe810, a348bbd2