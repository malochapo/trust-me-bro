Four commits changed the snooze or dedup decision or its time windows since 2025-05-22:

- **a348bbd2** (2025-05-29), `fix(signal): don't dedup on canary signals (#6026)`: canary signal instances are now skipped by deduplication and excluded from the dedup lookup.
- **7a9fe810** (2025-06-19), `feat(signal): make the default deduplication window configurable`: the default dedup lookback changed from a hardcoded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, defaulting to 45 minutes.
- **086dc910** (2025-08-07), `refactor(signal): simplify snooze filter checks`: the snooze check now skips any filter that isn't in active mode or isn't a snooze action, and an expired filter now ends the loop with `break` instead of `continue`. That changes which filters are evaluated.
- **917a0b7b** (2025-08-14), `refactor(signal): share the lookback window computation`: the per-filter dedup window changed from `timedelta(minutes=f.window)` to `timedelta(seconds=f.window)`, with a comment saying `SignalFilter.window` is stored in seconds. If that stored value was minutes before, the effective window is now 60 times shorter. I did not check the model or migrations to confirm the unit, so this should be verified.

I excluded the UI-only commits that touched snooze counts or views (5e136d7b, 90f73fe2) and the log-outcome and redaction commits (4474af25, d2675cf4), since they don't change the decision.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b