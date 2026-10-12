Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. The code is in `src/dispatch/signal/service.py` (`filter_snooze`, `filter_dedup`) and `src/dispatch/config.py`. I made no changes.

1. **`a348bbd2` (2025-05-29, "don't dedup on canary signals", #6026)**
   - `filter_dedup` now returns immediately if the incoming instance is a canary.
   - Both dedup queries also exclude earlier canary instances (`~SignalInstance.canary`), so a canary can never be the instance a new signal is deduplicated against.
   - It did not change any window.

2. **`7a9fe810` (2025-06-19, "make the default deduplication window configurable")**
   - The window for signals that have no filters at all used to be hard-coded at `timedelta(hours=1)`.
   - It is now read from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, a new setting in `config.py` (env var of the same name, cast to int).
   - **The default is 45 minutes, not the old 60.** This is a silent behaviour change for deployments that don't set the variable.

3. **`086dc910` (2025-08-07, "simplify snooze filter checks")**
   - In `filter_snooze`, the separate checks for a missing mode and a missing action (each with a log warning) are merged into one condition: skip unless the filter's mode is active and its action is snooze.
   - A filter with an empty mode or action is now skipped silently, without the warning.
   - **Behaviour change:** when a snooze filter's expiration is already past, the loop now does `break` instead of `continue`. An expired snooze filter therefore stops evaluation of the signal's remaining filters. That can skip a later, still-valid snooze filter.
   - A snooze filter has no lookback window. It is bounded by its `expiration` timestamp, which is compared against the current UTC time.

4. **`917a0b7b` (2025-08-14, "share the lookback window computation")**
   - It adds a `_window_start(seconds)` helper that returns the current UTC time minus that many seconds.
   - Default window (no filters): `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`. That is 45 minutes, or 2700 seconds, unless the env var overrides it. The result is the same as before the commit.
   - Per-filter window: `_window_start(f.window)`, so `SignalFilter.window` is now treated as **seconds**. Before this commit it was passed as `timedelta(minutes=f.window)`.
   - The model column `SignalFilter.window` (`signal/models.py:206`) is an integer in seconds, with a default of `60 * 60` (one hour). The commit's comment says the same.
   - This is a fix to match the column's real unit, but it also changes behaviour. For example, a stored window of 600 was previously applied as 600 minutes and is now 10 minutes.

**How the windows apply today**

| Case | Lookback window |
|---|---|
| Signal with no filters | `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` minutes (default 45), converted to seconds |
| Signal with a deduplicate filter | `filter.window` seconds (column default 3600) |
| Snooze filter | No lookback; active until its `expiration` |

One loose end: `signal/models.py:282` has a Pydantic schema with `window: int | None = 600`. I did not check whether the UI sends seconds or minutes.

----- next turn -----

The commit that broke deduplication windows is `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14). The new regression test fails on the old code and passes with the fix. All of `tests/signal` passes: 33 passed, 1 skipped.

**Cause.** Before that commit, the filter's window was applied as `timedelta(minutes=f.window)`. The UI field is labelled "Window (minutes)", and existing rows hold minutes. The refactor added a helper that takes seconds and passed `f.window` straight into it, with a comment saying the window is stored in seconds. A window of 30 therefore became 30 seconds, so two instances ten minutes apart no longer deduplicated.

**Fix.**
- `src/dispatch/signal/service.py`: the filter window is now converted with `(f.window or 0) * 60`. Existing filters work without being edited, since no stored data changes.
- `src/dispatch/signal/models.py`: I corrected the misleading "seconds" comment on the column. I also changed the column default from `3600` to `60`, so a new filter created without a window gets one hour rather than 3600 minutes. That default only affects new rows.

**Test.** `test_filter_actions_deduplicate_window_is_in_minutes` uses a window of 30 and an instance from 10 minutes earlier. The second instance must join the first one's case.

Existing tests that attach a filter with `signal.filters.append(SignalFilterFactory(...))` never actually attach it, so `signal.filters` is empty when `filter_dedup` runs. They end up exercising the default window instead. The new test calls `session.add` on the filter first. I left the old tests alone.

The default window for signals with no filter is 45 minutes (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, made configurable in `7a9fe810`). The `filter_signal` docstring still says "1-hour window", which is stale. I didn't change it.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES