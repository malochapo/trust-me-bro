Four commits since 2025-05-22 changed how Dispatch decides snooze or dedup. All four touch `src/dispatch/signal/service.py`.

- **a348bbd2** (2025-05-29, "don't dedup on canary signals"): `filter_dedup` now returns early for canary instances. Canary instances are also excluded from the dedup lookups.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the default dedup window for signals with no filters was 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): this is presented as a refactor, but it changes behaviour. When a snooze filter has expired, `filter_snooze` now does `break` instead of `continue`, so later filters are no longer checked.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): this is also presented as a refactor. Per-filter dedup windows (`f.window`) were computed as minutes and are now computed as seconds, via a new `_window_start` helper. The default window is still 45 minutes, converted to seconds.

I left out `4474af25` (adds logging) and `d2675cf4` (redacts raw fields before processing). Neither changes the snooze or dedup decision.

COMMITS: a348bbd267238b110a5d25fabb1e4e2380630831, 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651, 086dc910c308c8e5a91f5be8b4624cce11feae85, 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771