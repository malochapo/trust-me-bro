Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All four change `src/dispatch/signal/service.py`, in `filter_snooze` or `filter_dedup`.

- **a348bbd2** (2025-05-29, "don't dedup on canary signals"): `filter_dedup` now returns early for canary instances. Canary instances are also excluded from the dedup queries, both for the default window and for filter-based dedup.
- **7a9fe810** (2025-06-19, "make the default deduplication window configurable"): the default dedup window, used when a signal has no filters, was a hardcoded 1 hour. It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, set in `config.py` and defaulting to 45 minutes.
- **086dc910** (2025-08-07, "simplify snooze filter checks"): labelled a refactor, but it changes behaviour. When a snooze filter has expired, `filter_snooze` now does `break` instead of `continue`, so it stops checking the remaining filters. It also drops the warnings for a filter with no mode or no action.
- **917a0b7b** (2025-08-14, "share the lookback window computation"): also labelled a refactor, but it changes the time window. Per-filter dedup used `timedelta(minutes=f.window)`. It now uses `_window_start(f.window)`, which treats `SignalFilter.window` as seconds. The default window is still computed in minutes.

I left out other signal commits that only touch UI, logging, redaction or stats. Examples are 4474af25, d2675cf4, 01c28ff0, 5e136d7b and 90f73fe2. They don't change how a snooze or dedup decision is made.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b