Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated, including the time windows. I read the diffs for each.

- **a348bbd2** (2025-05-29, "don't dedup on canary signals"): `filter_dedup` now returns early for canary signals. The default-window query also ignores canary instances.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the default dedup window is now set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (default 45). It was a hard-coded one hour.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): `filter_snooze` now skips any filter that isn't both active and a snooze action. It also does `break` instead of `continue` when a snooze filter has expired, so any filters after an expired one are no longer checked. Despite the "refactor" label, that is a behaviour change.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): the dedup window is now computed through a shared `_window_start(seconds)` helper. Per-filter windows were previously read as minutes and are now read as seconds, and the default window is converted from minutes to seconds. Despite the "refactor" label, this changes the window length a per-filter `window` value produces.

I excluded commits that touch signals or the dedup config without changing the snooze or dedup decision:
- **4474af25** only adds logging.
- **d2675cf4** only masks sensitive raw fields.
- **50cf8979** and **90f73fe2** only change signal stats.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b

Note that the last line has to carry at least 8 characters per hash, and the hashes above are exactly 8.

COMMITS: a348bbd2,7a9fe810,086dc910,917a0b7b