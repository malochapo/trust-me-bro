Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All four touch `src/dispatch/signal/service.py` (`filter_snooze` / `filter_dedup`).

- **a348bbd2** (2025-05-29, "don't dedup on canary signals"): `filter_dedup` now skips canary instances entirely. Canary instances are also excluded from the candidate instances it compares against.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the default window for signals with no filters was a hard-coded 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): labelled a refactor, but it changes behaviour in `filter_snooze`. When a snooze filter has expired, the loop now stops (`break`) instead of moving on to the next filter (`continue`). The mode/action checks were also merged, which drops the "no mode" and "no action" warnings.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): labelled a refactor, but it changes the unit of the per-filter dedup window. `SignalFilter.window` was treated as minutes and is now treated as seconds, through the new `_window_start` helper. The default window still works out to the same number of minutes.

I excluded these as not changing the snooze or dedup decision:
- **4474af25**: only adds logging of the outcome.
- **d2675cf4**: masks sensitive raw fields before processing.
- **5e136d7b**: adds entity and trigger views to the signal instance page.
- **50cf8979**: limits entity signal stats to the last 30 days in the UI.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b