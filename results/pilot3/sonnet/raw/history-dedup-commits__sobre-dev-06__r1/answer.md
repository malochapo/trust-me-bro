Four commits since 2025-05-22 changed how Dispatch decides whether a signal instance is snoozed or deduplicated. All four are in `src/dispatch/signal/service.py`.

- **a348bbd2** (2025-05-29, "don't dedup on canary signals"): `filter_dedup` now returns early for canary instances. Canary instances are also excluded from the instances it matches against.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the default dedup window for signals with no filters was a hard-coded 1 hour. It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, a new setting in `config.py`.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): `filter_snooze` was refactored. It also changed behaviour: an expired snooze filter now does `break` instead of `continue`, so the loop stops at the first expired filter and later filters are never checked. It also drops the "no mode" and "no action" warning logs.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): this adds a `_window_start(seconds)` helper. It looks like a pure refactor, but the per-filter window changes from `timedelta(minutes=f.window)` to seconds. `SignalFilter.window` is stored in seconds, so this changes the effective dedup window for filtered signals. The default window is still minutes × 60.

I left out these commits that touch signal processing but not the snooze/dedup decision or its windows:
- 4474af25 only adds logging of each instance's outcome.
- d2675cf4 only masks sensitive raw fields.
- 50cf8979 limits the UI's entity signal stats to 30 days.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b