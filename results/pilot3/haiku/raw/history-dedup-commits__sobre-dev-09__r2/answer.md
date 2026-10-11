Four commits since 2025-05-22 changed how Dispatch decides whether a signal instance is snoozed or deduplicated, or the time windows used for that. I checked every commit that touched the signal code or the related config and filter models.

- **a348bbd2** (2025-05-29), `fix(signal): don't dedup on canary signals (#6026)`: canary signal instances are now excluded from the deduplication query.
- **7a9fe810** (2025-06-19), `feat(signal): make the default deduplication window configurable`: the default dedup window changed from a hardcoded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which defaults to 45 minutes.
- **086dc910** (2025-08-07), `refactor(signal): simplify snooze filter checks`: despite the title, this changes behavior. Only active snooze filters are considered now, and an expired filter now `break`s out of the loop instead of `continue`, so later filters are skipped.
- **917a0b7b** (2025-08-14), `refactor(signal): share the lookback window computation`: also a behavior change despite the title. The per-filter dedup window was previously read as minutes (`timedelta(minutes=f.window)`) and is now read as seconds (`_window_start(f.window)`). Anyone relying on the old unit for existing filters would see different windows.

I excluded commits that only add logging or unrelated features. `4474af25` adds outcome logging in `signal/flows.py` without changing any decision. `d2675cf4` and `dee1699d` don't touch snooze or dedup logic.

COMMITS: a348bbd2, 7a9fe810, 086dc910, 917a0b7b