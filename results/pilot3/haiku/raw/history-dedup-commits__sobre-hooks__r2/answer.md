Four commits changed how Dispatch decides snooze or dedup, including the time windows. Each one touches `src/dispatch/signal/service.py` and changes the decision path or a window:

- **`a348bbd2`** (2025-05-29), "don't dedup on canary signals": `filter_dedup` now returns early for canary instances and excludes canary instances from the match queries.
- **`7a9fe810`** (2025-06-19), "make the default deduplication window configurable": the default window moved from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45 minutes.
- **`086dc910`** (2025-08-07), "simplify snooze filter checks": the snooze check now uses `break` instead of `continue` when a snooze has expired. This is a behaviour change, not just a refactor.
- **`917a0b7b`** (2025-08-14), "share the lookback window computation": the dedup window computation moved into `_window_start`. It also changed how `SignalFilter.window` is converted: it is now treated as seconds, not minutes.

I excluded these commits from the 2025-05-22 onward range:
- `d2675cf4` (masks raw fields before processing) and `4474af25` (logs signal outcomes): both touch `flows.py` only, not the snooze or dedup logic.
- `5e136d7b` (entity and trigger views on the signal instance page): UI and model changes only.

The keyword search and the `-S'window'` pickaxe search found no other commits in this area.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b