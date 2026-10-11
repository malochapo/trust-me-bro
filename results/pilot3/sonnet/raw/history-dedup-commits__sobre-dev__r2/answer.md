Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated:

- **a348bbd2** (2025-05-29), "don't dedup on canary signals": changes the dedup decision in `filter_dedup` so canary signals are not deduplicated.
- **7a9fe810** (2025-06-19), "make the default deduplication window configurable": the default dedup window used when a signal has no filters is now set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- **086dc910** (2025-08-07), "simplify snooze filter checks": mostly a simplification, but it also changes behaviour. When it meets an expired snooze filter it now stops checking (`break`) instead of moving on to the next filter (`continue`). It also drops the warnings for filters with no mode or action.
- **917a0b7b** (2025-08-14), "share the lookback window computation": this adds `_window_start(seconds)` and uses it for both windows. The per-filter `f.window` was previously treated as minutes. It is now treated as seconds, which changes the dedup window actually applied.

I left out two nearby signal commits that don't touch the snooze or dedup decision:

- **4474af25** only adds log lines.
- **d2675cf4** redacts sensitive fields in the raw payload and adds a config setting for them.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b