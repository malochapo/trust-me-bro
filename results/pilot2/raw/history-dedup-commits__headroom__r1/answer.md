Four commits since 2025-05-22 changed how a new signal instance is snoozed or deduplicated. All four are in `src/dispatch/signal/service.py`. `7a9fe810` also touches `src/dispatch/config.py`.

- **`a348bbd2`** (2025-05-29, "don't dedup on canary signals"): `filter_dedup` now returns early for canary signals. Canary instances are also excluded from the candidate instances it matches against.
- **`7a9fe810`** (2025-06-19, "make the default deduplication window configurable"): the default dedup window, used when a signal has no filters, was a hard-coded 1 hour. It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, with a default of 45 minutes.
- **`086dc910`** (2025-08-07, "simplify snooze filter checks"): it is labelled a refactor, but `filter_snooze` behaves differently. An expired snooze filter now ends the loop (`break`) instead of skipping to the next filter (`continue`). Filters with a missing mode or action are no longer logged with a warning; the skip is now silent.
- **`917a0b7b`** (2025-08-14, "share the lookback window computation"): it is also labelled a refactor, but it changes the window unit. Per-filter `f.window` was treated as minutes and is now treated as seconds, through the new `_window_start` helper. The default-window calculation keeps its old value because the minutes are multiplied by 60.

I left out `5e136d7b`. It added a UI table for snoozes but doesn't change the decision logic.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b