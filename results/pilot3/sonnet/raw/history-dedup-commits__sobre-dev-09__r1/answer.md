Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I checked each one's diff. Searching the history for dedup and snooze changes turned up `dee1699d` as well, but it is about security-event suggestions, so I left it out. I did not read its diff.

- **`a348bbd2`** (fix: don't dedup on canary signals): canary instances now skip deduplication, and canary signals are excluded when looking for matching earlier instances.
- **`7a9fe810`** (make the default dedup window configurable): the default dedup window was a fixed 1 hour. It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
- **`086dc910`** (simplify snooze filter checks): in the snooze filter loop, a filter that isn't active or isn't a snooze action now ends the loop (`continue` became `break`) instead of being skipped. This changes which filters get evaluated. It also drops the warnings for filters with no mode or no action.
- **`917a0b7b`** (share the lookback window computation): a new `_window_start(seconds)` helper replaces the inline window calculation. The snooze filter's `f.window` was previously treated as minutes and is now treated as seconds. The default dedup window is passed as minutes times 60, so it is unchanged. This commit changes the time window used for snoozing.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b