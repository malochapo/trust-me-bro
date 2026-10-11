Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated, including the time windows:

- **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals*: canary instances skip deduplication entirely, both in the early return and in the duplicate query.
- **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*: replaces the hardcoded 1-hour default dedup window with `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (default 45).
- **`086dc910`** (2025-08-07), *simplify snooze filter checks*: folds the mode/action checks into one condition and changes the expired-snooze branch from `continue` to `break`, so later snooze filters are no longer evaluated once an expired one is hit.
- **`917a0b7b`** (2025-08-14), *share the lookback window computation*: a refactor that also changes units. Per-filter dedup windows were computed as `timedelta(minutes=f.window)` and are now `_window_start(f.window)`, which treats `f.window` as seconds.

I left out `4474af25` (logging only), `d2675cf4` (redaction of raw payloads before processing, not a snooze/dedup decision) and `5e136d7b` (UI and model rebuild only). I searched the commit history by keyword (snooze, dedup, window, lookback) and by file history for `src/dispatch/signal/`, then read the diffs of the candidates.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b