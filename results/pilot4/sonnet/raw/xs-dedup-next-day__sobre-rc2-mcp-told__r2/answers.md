Four commits since 2025-05-22 changed how a new signal instance is snoozed or deduplicated. Nothing was modified. The logic is in `src/dispatch/signal/service.py` (`filter_snooze`, `filter_dedup`).

1. **`a348bbd2` (2025-05-29), "fix(signal): don't dedup on canary signals (#6026)"**
   - `filter_dedup` now returns immediately when the incoming instance is a canary.
   - Canary instances are also excluded as dedup candidates, using `~SignalInstance.canary`, in both the default no-filter query and the per-filter query.
   - It adds no time window and changes none.

2. **`7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
   - The window for signals with no filters was a hard-coded `timedelta(hours=1)`.
   - It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`, an int env var.
   - The default in the code today is **45 minutes**, not the old 1 hour.

3. **`086dc910` (2025-08-07), "simplify snooze filter checks"**
   - It collapses the separate mode and action checks in `filter_snooze` into one condition: skip a filter unless it is `active` and its action is `snooze`.
   - It drops the "no mode" and "no action" warnings.
   - It also makes one behaviour change. An expired snooze filter (`expiration <= now`, compared in UTC) used to `continue` to the next filter. It now does `break`, so any later filters on that signal are no longer checked.
   - A snooze filter with no expiration is still warned about and skipped. The snooze deadline is an absolute `expiration` timestamp rather than a duration.

4. **`917a0b7b` (2025-08-14), "share the lookback window computation"**
   - It adds `_window_start(seconds)`, which returns `now(UTC) - timedelta(seconds=seconds)`, and both dedup paths now use it.
   - **Default window:** `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`. That is still 45 minutes, now expressed in seconds.
   - **Per-filter window:** `_window_start(f.window)`. Before this commit the code was `timedelta(minutes=f.window)`.
     - `SignalFilter.window` is an integer number of **seconds**. The column default is `60 * 60`, which is 3600 s (1 hour), and the Pydantic model default is `600` (10 minutes).
     - The old code treated those numbers as minutes, so this commit corrects the unit.
     - A stored value of 3600 used to mean a 60-hour window. It now means 1 hour.

I checked the other commits that touched the signal files in this period, such as `4474af25`, which adds logging, and `d2675cf4`, which masks sensitive fields. They don't change snooze or dedup decisions.

----- next turn -----

Commit `917a0b7b` ("refactor(signal): share the lookback window computation", 2025-08-14) caused the bug. I fixed it and added a regression test. The signal tests pass, 15 passed and 1 skipped. The new test fails without the fix.

**Cause:** The commit assumed `SignalFilter.window` was stored in seconds. It changed `timedelta(minutes=f.window)` to `timedelta(seconds=f.window)`. The UI field is labelled "Window (minutes)" and the stored values are minutes, so a window of 30 became 30 seconds. Two instances ten minutes apart no longer matched, and each opened its own case.

**Fix:**
- **Window unit:** `_window_start` in `src/dispatch/signal/service.py` now takes minutes. The default-window call no longer multiplies by 60. Stored values were always minutes, so existing filters work without any edit or migration.
- **Stale text:** I corrected the misleading "seconds" comment on the model column and the "1-hour" text in the `filter_signal` docstring.
- **Regression test:** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It sets a window of 30 with an earlier instance 10 minutes old, and checks the new instance is deduplicated into the existing case.

**One more problem I did not fix:** `086dc910` ("simplify snooze filter checks") changed `continue` to `break` for expired snooze filters in `filter_snooze`. An expired filter now stops the loop, so any snooze filters after it are skipped. You'll probably want to look at that.

The canary commit is `a348bbd2`. It makes `filter_dedup` return early for canary instances and excludes canary instances from the matching queries. The default window was first made configurable in `7a9fe810`.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd267238b110a5d25fabb1e4e2380630831
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES