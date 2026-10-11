Four commits since 2025-05-22 changed the snooze/dedup decision or its time windows:

- **a348bbd2** (2025-05-29, "fix(signal): don't dedup on canary signals"): canary signals are now excluded from deduplication, so they never match or get marked as duplicates.
- **7a9fe810** (2025-06-19, "feat(signal): make the default deduplication window configurable"): the default dedup window for signals with no dedup filter was a hard-coded 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
- **086dc910** (2025-08-07, "refactor(signal): simplify snooze filter checks"): labelled a refactor, but it changes behaviour. When a snooze filter has expired, the loop now `break`s instead of `continue`ing, so later snooze filters on the signal are no longer evaluated. The removed warning checks don't change outcomes.
- **917a0b7b** (2025-08-14, "refactor(signal): share the lookback window computation"): also changes the window. Dedup filter windows were read as minutes (`timedelta(minutes=f.window)`); the new `_window_start(f.window)` treats the value as seconds, with a comment saying `SignalFilter.window` is stored in seconds. The default window is now converted to seconds before use. Whether this changes effective windows depends on how existing filter values are stored, which I didn't check.

I excluded commits that only touched snooze/dedup code paths without changing their logic, such as d2675cf4 (masking raw fields) and 4474af25 (logging outcomes), along with the UI-only commits.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b