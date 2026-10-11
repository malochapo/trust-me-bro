Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I read the diffs for each. Other signal commits in the period, such as `4474af25` (outcome logging) and `d2675cf4` (field masking), don't touch that decision logic. The others that mention "window" are UI or stats changes.

- **`a348bbd2`** (2025-05-29): `filter_dedup` now skips deduplication for canary signals. Canary instances are also excluded when searching for earlier instances to match against.
- **`7a9fe810`** (2025-06-19): the default dedup window, used for signals with no filters, was hard-coded at 1 hour. It is now read from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
- **`086dc910`** (2025-08-07): the snooze filter checks in `filter_snooze` were simplified. Besides dropping the warnings for a missing mode or action, an expired snooze filter now ends the loop (`break`) instead of moving on to the next filter (`continue`).
- **`917a0b7b`** (2025-08-14): the lookback window computation was refactored into a shared `_window_start(seconds)` helper. The per-filter dedup window (`f.window`) was previously treated as minutes and is now treated as seconds. That is a real change to the time window, even though the commit is labelled a refactor.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b