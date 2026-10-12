Five commits since 2025-05-22 touched snooze or dedup decisions. Four of them changed behaviour and one is a refactor with a side effect. Everything below is from reading the diffs and the current code in `src/dispatch/signal/service.py`. I haven't run anything, and I made no code changes.

**Commits that changed behaviour**

1. **`a348bbd2` (2025-05-29), "don't dedup on canary signals" (#6026)**
   - `filter_dedup` now returns right away when the incoming instance is a canary, so canaries are never deduplicated.
   - Both dedup queries (the default one and the per-filter one) now exclude earlier canary instances with `~SignalInstance.canary`. A canary can no longer be the case that a new signal gets attached to.
   - No windows changed.

2. **`7a9fe810` (2025-06-19), default dedup window made configurable**
   - The default window applies to signals that have no filters at all. It was hard-coded to `timedelta(hours=1)`.
   - It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`, an int that defaults to **45 minutes**.
   - This quietly shortened the default from 60 to 45 minutes.

3. **`917a0b7b` (2025-08-14), "share the lookback window computation"**
   - It added `_window_start(seconds)`, which returns `now(UTC) - timedelta(seconds=seconds)`.
   - Default window: calls `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`. That is still 45 minutes, expressed as 2700 seconds, so there is no change here.
   - Per-filter window: this is the real behaviour change. It used to be `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, which treats the value as **seconds**.
     - The model says `SignalFilter.window` is in seconds and defaults to `60 * 60`, which is 3600 s or 1 hour.
     - The pydantic schema default is 600, which is 600 s or 10 minutes.
     - The old minutes interpretation dates from `9c523348` in 2023. It made per-filter windows 60 times longer than intended, so a stored 3600 meant 60 hours. This commit fixes that, but the message calls it a refactor.

4. **`086dc910` (2025-08-07), "simplify snooze filter checks"**
   - Active filters are still the only ones considered, and the action must be snooze.
   - It removed the warnings for a missing mode or action.
   - A missing mode or action now just fails the combined `continue` check, so the outcome is the same.
   - The behaviour change is for an expired snooze filter (expiration at or before now). It used to `continue` to the next filter. It now does `break`, which stops checking all remaining filters for that instance.
     - If an expired snooze filter comes before an unexpired one in the list, the unexpired snooze is no longer applied.
   - A snooze filter has an expiration datetime rather than a window. That expiration is compared against the current UTC time.

**Not a decision change**
- `4474af25` (2025-06-10) only adds logging of the outcome in `flows.py`.

**Current state**
- `filter_signal` runs `filter_snooze` first. It runs `filter_dedup` only if the instance wasn't snoozed.
- The `filter_signal` docstring still says the default dedup window is 1 hour. That is stale, because the code uses 45 minutes by default.
- In `flows.py`, `timedelta(seconds=5)` is a throttle on Slack thread updates for deduplicated signals. It doesn't decide whether an instance is deduplicated, and I found no commit since 2025-05-22 that changed it.

----- next turn -----

I saved the findings to memory in `signal-snooze-dedup-history.md` and added a pointer to it in `MEMORY.md`. It records the four behaviour-changing commits (`a348bbd2`, `7a9fe810`, `917a0b7b`, `086dc910`), the window values and units, and the stale "1 hour" docstring. A new session can pick it up from there. No code was changed.

----- next turn -----

The commit that broke it is `917a0b7b` (2025-08-14), labelled "refactor(signal): share the lookback window computation". The fix is in and the new regression test passes. The signal tests pass: 33 passed, 1 skipped.

**Cause:** the refactor changed the per-filter dedup lookback from `timedelta(minutes=f.window)` to `timedelta(seconds=f.window)`. The UI labels the field "Window (minutes)" and existing rows store minutes, so a window of 30 became 30 seconds. Two instances ten minutes apart then fell outside the window and opened separate cases.

**Fix:**
- **Window unit:** in `src/dispatch/signal/service.py`, `filter_dedup` now uses `_window_start(f.window * 60)`, so the window is in minutes again. Stored values are unchanged, so existing filters work without being edited and no migration is needed.
- **Defaults:** in `src/dispatch/signal/models.py` I also changed the defaults that had been written as seconds, because they would now mean 60 hours and 10 hours. The model default goes from 3600 to 60 and the schema default from 600 to 10. Both still mean 1 hour and 10 minutes.

**Regression test:** `test_filter_dedup_window_is_in_minutes` uses a filter with a 30-minute window and an earlier instance 10 minutes old that already has a case. It asserts the new instance is deduplicated into that case. With the source fix stashed, it fails.

**Canary:** `a348bbd2` (2025-05-29) made canary instances skip dedup and excluded earlier canary instances from dedup queries.

**Default window:** signals with no filter group instances within 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`. Commit `7a9fe810` introduced that setting. The `filter_signal` docstring still says 1 hour, which is out of date.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES