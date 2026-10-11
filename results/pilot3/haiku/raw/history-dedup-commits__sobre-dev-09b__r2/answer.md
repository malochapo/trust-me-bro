Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated, or the time windows involved. All of them touch `src/dispatch/signal/service.py`:

- **a348bbd2** (2025-05-29), `fix(signal): don't dedup on canary signals`: `filter_dedup` now skips canary instances, and canary instances are excluded from the dedup match queries.
- **7a9fe810** (2025-06-19), `feat(signal): make the default deduplication window configurable`: the one-hour default dedup window became `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, defaulting to 45 minutes (added in `src/dispatch/config.py`).
- **086dc910** (2025-08-07), `refactor(signal): simplify snooze filter checks`: this is a behaviour change, not just a refactor. An expired snooze filter now `break`s out of the loop where it previously `continue`d, so later filters are no longer evaluated.
- **917a0b7b** (2025-08-14), `refactor(signal): share the lookback window computation`: this also changes the window semantics. Per-filter `f.window` is now treated as seconds (`_window_start(f.window)`), where the previous code multiplied it as minutes.

Excluded, with reasons:
- **d2675cf4** (`mask sensitive raw fields before processing`) redacts `raw` before entity extraction. Dedup matches on entities, so this affects its input indirectly, but it does not change the snooze or dedup decision itself. It is borderline; say if you want it included.
- **4474af25** only adds logging.
- **5e136d7b** and **01c28ff0** are UI and API changes.
- Other commits that matched the keywords were UI, Slack, or test changes.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b