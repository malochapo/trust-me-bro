Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All four touch `src/dispatch/signal/service.py`, which holds `filter_snooze` and `filter_dedup`.

- **a348bbd2** (2025-05-29, "don't dedup on canary signals"): `filter_dedup` now returns early for canary instances. Canary instances are also excluded from the candidate instances it matches against, in both the default one-hour window and the per-filter windows.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the hard-coded one-hour default dedup window is now set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): this is labelled a refactor but it changes behaviour. In `filter_snooze`, an expired snooze filter now ends the loop with `break`, where before it was skipped with `continue`. The commit also removes the warnings and early skips for filters with no mode or no action.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): this is also labelled a refactor and also changes behaviour. The per-filter dedup window `f.window` is now read as seconds, where before it was read as minutes. The default window still comes out as minutes.

I excluded two commits that matched the search terms:

- **dee1699d** only adds a default of `None` to a project snooze-extension field.
- **5e136d7b** only adds UI views.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b