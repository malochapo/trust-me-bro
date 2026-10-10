Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All four touch `src/dispatch/signal/service.py` (`filter_snooze` or `filter_dedup`).

- **a348bbd2** (2025-05-29, "don't dedup on canary signals"): `filter_dedup` now returns early for canary signals. Canary instances are also excluded from the candidate set in both the default and per-filter dedup queries. The 1-hour default window is unchanged.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the hardcoded 1-hour default dedup window becomes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, added in `config.py`.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): despite the "refactor" label, this changes `filter_snooze` behavior. An expired snooze filter now ends the loop (`break`) instead of moving on to the next filter (`continue`). It also drops the warnings for a missing mode or action. A filter with no mode or no action is now skipped silently.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): this adds a `_window_start(seconds)` helper. The default window is converted to seconds, so it behaves the same. Per-filter windows were previously read as minutes and are now read as seconds, which changes the effective window for those filters.

I left out `5e136d7b`, which only adds UI views for snoozes, and `01c28ff0`, `90f73fe2` and `dee1699d`. The last three touched `service.py` or matched the search, but their diffs don't change the snooze or dedup decision.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b