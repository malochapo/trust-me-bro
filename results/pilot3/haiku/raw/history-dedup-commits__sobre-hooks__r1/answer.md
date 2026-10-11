Four commits since 2025-05-22 changed the snooze or dedup decision or its time windows:

- **a348bbd267238b110a5d25fabb1e4e2380630831** (2025-05-29): "fix(signal): don't dedup on canary signals". Canary instances are skipped in `filter_dedup` and excluded from the candidate matches.
- **7a9fe8103c31b500dbb68f9db7ecc76a5fca5651** (2025-06-19): "make the default deduplication window configurable". The default window for signals without a dedup filter moved from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45.
- **917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771** (2025-08-14): "share the lookback window computation". Per-filter dedup windows are now read as seconds (`_window_start(f.window)`) instead of minutes. This changes the effective window for existing filters.
- **086dc910c308c8e5a91f5be8b4624cce11feae85** (2025-08-07): "simplify snooze filter checks". In `filter_snooze`, an expired snooze now `break`s the loop instead of `continue`, so later snooze filters on the signal are no longer checked.

I left out commits that touch the same files but don't change these decisions. Examples are 4474af2 (logging only), d2675cf (redaction before processing), 01c28ff0 and 90f73fe2 (frontend snooze/duplicate display and counts), and 5e136d7 (instance page views).

COMMITS: a348bbd267238b110a5d25fabb1e4e2380630831, 7a9fe8103c31b500dbb68f9db7ecc76a5fca5651, 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771, 086dc910c308c8e5a91f5be8b4624cce11feae85