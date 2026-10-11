Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All four touch `src/dispatch/signal/service.py`.

- **a348bbd2** (2025-05-29, "don't dedup on canary signals"): `filter_dedup` now returns early for canary instances. It also ignores existing canary instances when looking for a match. It does not change the time windows.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the hard-coded 1-hour default dedup window became `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, added in `config.py`.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): despite the "refactor" label, `filter_snooze` behaves differently. An expired snooze filter now ends the loop with `break`, where it used to `continue` to the next filter. The explicit checks for a missing mode or action were also folded into one condition.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): this adds a shared `_window_start(seconds)` helper. Per-filter dedup windows (`f.window`) used to be read as minutes and are now read as seconds. The default window is converted from minutes to seconds. This changes the window length for filters.

I left out the other signal commits in that period because they don't touch the snooze or dedup decision:
- **4474af25**: logs the outcome of each processed signal instance.
- **d2675cf4**: masks sensitive raw fields before processing.
- **5e136d7b**: adds entity and trigger views to the signal instance page.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b