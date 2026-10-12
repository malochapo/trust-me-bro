Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I read the diffs and the current `src/dispatch/signal/service.py`, and changed nothing.

**Commits**

1. **`a348bbd2`** (2025-05-29), "don't dedup on canary signals (#6026)".
   - `filter_dedup` now returns early when the incoming instance is a canary.
   - Both dedup queries also exclude canary instances with `~SignalInstance.canary`: the default one and the per-filter one.
   - It changed no windows.

2. **`7a9fe810`** (2025-06-19), "make the default deduplication window configurable".
   - The default window for signals with no filters was hard-coded as `timedelta(hours=1)`. It now comes from the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`.
   - **The default is 45, in minutes.** That silently shortened the default from 60 to 45 minutes, and it can be overridden with an environment variable.

3. **`086dc910`** (2025-08-07), "simplify snooze filter checks".
   - It dropped the separate "no mode" and "no action" warning branches. It folded them into one check: skip unless the filter is `active` and its action is `snooze`.
   - It also changed what happens when a snooze filter has expired. That case was `continue` and is now `break`, so the first expired snooze filter stops the loop and later snooze filters are no longer checked. That looks like a behaviour change, not just a cleanup.
   - Snooze is decided by the filter's `expiration` timestamp, compared against `datetime.now(timezone.utc)`. There is no lookback window for snoozing.

4. **`917a0b7b`** (2025-08-14), "share the lookback window computation".
   - It added the helper `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
   - The default dedup call is now `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, which is still 45 minutes (2700 s) by default.
   - For per-filter dedup, the code used `timedelta(minutes=f.window)` and now uses `_window_start(f.window)`, so `f.window` is treated as seconds.
   - The `SignalFilter.window` column is documented as seconds, with a default of `60 * 60` (1 hour). The pydantic schema default is `600`, which is 10 minutes. So this commit probably fixed a unit bug where a value stored as seconds was being read as minutes. Existing filters with `window = 3600` would have been looked up over 3600 minutes before this change, and over 1 hour after it.

**How the windows apply today**

- **Order:** `filter_signal` runs `filter_snooze` first. It runs `filter_dedup` only if no filter action was set.
- **Snooze:** an active snooze filter applies if its `expiration` is in the future. If it has an expression, the instance must match it. With no expression, the instance is snoozed regardless of entities.
- **Default dedup:** this applies when the signal has no filters. The instance joins the most recent non-canary instance of the same signal that has a case and was created within the last 45 minutes (2700 s). The 45 comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, and the default is overridable.
- **Filter dedup:** each active deduplicate filter looks back `f.window` seconds. The instance joins the case of the earliest matching instance that shares an entity.

The `filter_signal` docstring still says "1-hour window", which is stale because the default is now 45 minutes.

----- next turn -----

The regression test fails on the old code and passes with the fix. The signal tests pass, with 33 passed and 1 skipped.

**Cause:** commit `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14). Before it, `filter_dedup` used `timedelta(minutes=f.window)`. The refactor added a `_window_start(seconds)` helper and passed it `f.window`, with a comment saying the window is stored in seconds. The window is stored in minutes, so a window of 30 became 30 seconds. Two instances ten minutes apart fell outside it and each opened a case.

Of the commits I found, the others don't touch the window:
- `a348bbd2` is the canary change.
- `7a9fe810` made the default window configurable.
- `086dc910` only simplified the snooze checks.

**Fix:**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The default-window call no longer multiplies by 60.
- `src/dispatch/signal/models.py`: corrected the misleading "seconds" comment on `SignalFilter.window`.
- Existing filters need no editing, because the stored values were always minutes.
- `tests/signal/test_signal_service.py`: new `test_filter_dedup_window_is_in_minutes`. It uses a window of 30 and an instance from 10 minutes earlier.

**Defaults I left alone:** the column default is `60 * 60` and the pydantic default is `600`. Both are now read as minutes, which is probably not what was intended. I left them because changing them would alter new filters.

**Test gotcha:** `signal.filters.append(SignalFilterFactory(...))` silently attaches nothing, because the factory commits while the collection is being evaluated. Existing tests that use this pattern may be passing through the default window without exercising their filter. I didn't check or change them.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES