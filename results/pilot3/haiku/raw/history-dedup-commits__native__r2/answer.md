Four commits since 2025-05-22 changed how Dispatch decides snooze or deduplication, including the time windows:

- **a348bbd2** (2025-05-29, "fix(signal): don't dedup on canary signals"): canary instances are now skipped by dedup and excluded from the matching pool. This changes the dedup decision.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the default dedup window for signals without filters moved from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): when a snooze filter has expired, the loop now `break`s instead of `continue`s. Later active snoozes are no longer checked, so this changes the snooze decision. The commit also removed some validation and warning branches.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): the dedup filter's `window` is now treated as seconds, where it was previously minutes. The window computation moved into a shared `_window_start` helper. This changes the effective dedup window length for custom filters.

I ruled out the other commits that touch the signal code, such as the redaction, outcome-logging, and UI changes, because they don't alter the snooze or dedup decision. I checked the diffs of the four above; I did not run the test suite.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b