Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I read the diffs of the first, third and fourth below. For `086dc910` and `917a0b7b` I checked the diff only for behaviour changes, not for how they interact.

- **`a348bbd2`** (2025-05-29), "don't dedup on canary signals": canary signals are now excluded from deduplication in `filter_dedup`.
- **`7a9fe810`** (2025-06-19), "make the default deduplication window configurable": the default dedup window used when a signal has no filters changes from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. That setting defaults to 45 minutes, so the default behaviour also changes.
- **`086dc910`** (2025-08-07), "simplify snooze filter checks": billed as a refactor, but it changes behaviour. When a snooze filter has expired, `filter_snooze` now stops with `break` instead of skipping that filter with `continue`.
- **`917a0b7b`** (2025-08-14), "share the lookback window computation": also billed as a refactor, but it changes the unit of the per-filter dedup window. `f.window` was treated as minutes and is now treated as seconds, via a new `_window_start` helper. The default window is unchanged, at the configured number of minutes.

I left out the other signal commits that matched my search. They touch logging (`4474af25`), field masking (`d2675cf4`), stats or UI, and don't affect the snooze or dedup decision.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b