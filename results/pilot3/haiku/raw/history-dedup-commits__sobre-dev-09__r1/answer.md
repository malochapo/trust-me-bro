Four commits since 2025-05-22 changed how Dispatch decides whether a signal instance is snoozed or deduplicated, or the time windows involved. All are in `src/dispatch/signal/service.py`:

- **a348bbd2** (2025-05-29), `fix(signal): don't dedup on canary signals`: canary instances are excluded from deduplication, both as candidates and as matches.
- **7a9fe810** (2025-06-19), `feat(signal): make the default deduplication window configurable`: the default dedup window moves from a hardcoded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (default 45, added in `src/dispatch/config.py`).
- **086dc910** (2025-08-07), `refactor(signal): simplify snooze filter checks`: despite the title, this changes behavior. When a snooze filter's expiration has passed, the loop now `break`s instead of `continue`ing, so later filters are no longer evaluated. The per-filter warning logs were also dropped.
- **917a0b7b** (2025-08-14), `refactor(signal): share the lookback window computation`: the dedup window start is now computed by a shared `_window_start` helper. The diff shows it preserves the existing behavior, but it is the code that sets the window, so I included it.

I excluded commits that touch these areas without changing the decision or windows: d2675cf4 (masks raw fields before processing), 4474af25 (logs outcomes), and the UI-only changes in 5e136d7b, 90f73fe2, 01c28ff0 and dee1699d. I checked for other changes by searching the history for the window, snooze, and dedup terms across `src` and `tests`.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b