Four commits since 2025-05-22 changed how Dispatch decides whether a signal instance is snoozed or deduplicated. I read the diffs of each. `git log` shows no other commits to `signal/service.py`, `signal/flows.py` or `signal/models.py` in that period that touch this logic.

- **`a348bbd2` (2025-05-29), don't dedup on canary signals.** `filter_dedup` now returns early for canary instances. Canary instances are also excluded from the candidate matches in both the default and the filter-based dedup queries.
- **`7a9fe810` (2025-06-19), configurable default dedup window.** The window for signals with no dedup filter was a hard-coded 1 hour. It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
- **`086dc910` (2025-08-07), simplify snooze filter checks.** In `filter_snooze`, the mode and action checks were merged. An expired snooze filter now stops the loop with `break` instead of skipping to the next filter with `continue`. That changes which filters get evaluated.
- **`917a0b7b` (2025-08-14), share the lookback window computation.** The new `_window_start(seconds)` helper now computes the dedup windows. The per-filter window `f.window` used to be treated as minutes and is now treated as seconds. The default window is converted to seconds, so it stays the same.

I left out these commits because they don't change the decision or its windows:
- `4474af25` only adds log lines.
- `d2675cf4` masks sensitive raw fields before processing.
- The UI, stats and tags commits don't touch the decision.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b

Note: `git log` printed the hashes as 8 characters, and the line above uses those.

COMMITS: a348bbd2,7a9fe810,086dc910,917a0b7b