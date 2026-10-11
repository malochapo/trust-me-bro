Five commits since 2025-05-22 changed this logic. Two of the "refactor" commits also changed behavior. All of the logic is in `src/dispatch/signal/service.py` (`filter_snooze`, `filter_dedup`, `filter_signal`). I only read the code and git history and changed nothing.

**Commits**

1. **`a348bbd2`** (2025-05-29, "don't dedup on canary signals", #6026)
   - `filter_dedup` now returns immediately if the incoming instance is a canary.
   - Canary instances are also excluded as dedup matches, in both the default query and the per-filter query (`~SignalInstance.canary`).
   - It adds no window and changes no window value.

2. **`7a9fe810`** (2025-06-19, "make the default deduplication window configurable")
   - The default window applies to signals that have no filters at all. It was hard-coded as `timedelta(hours=1)`.
   - It now comes from the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`, an int env var that defaults to **45 minutes**.
   - This silently shortened the default from 60 to 45 minutes.

3. **`086dc910`** (2025-08-07, "simplify snooze filter checks")
   - It dropped the "no mode" and "no action" warnings and merged the two checks into one: skip the filter unless it is active and its action is snooze.
   - It also changed an expired snooze from `continue` to `break`. Once a snooze filter's `expiration` has passed, the loop stops and later snooze filters on that signal are no longer checked. That is a behavior change in a commit labelled as a refactor.
   - Snooze has no lookback window. It is bounded by each filter's absolute `expiration` timestamp.

4. **`917a0b7b`** (2025-08-14, "share the lookback window computation")
   - It added the `_window_start(seconds)` helper, which returns now minus `timedelta(seconds=...)`.
   - The default dedup call became `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`. That is still 45 minutes, so nothing changed there.
   - For per-filter dedup, the window was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, which is seconds. The code comment says `SignalFilter.window` is stored in seconds, so this effectively fixes a unit mismatch. It also changes behavior: a stored value of 3600 was previously applied as 3600 minutes (60 hours) and is now applied as 3600 seconds (1 hour).

`4474af25` (logging in `flows.py`) and `d2675cf4` and `5e136d7b` (raw-field masking and UI) touch these files but don't change the snooze or dedup decision.

**How it works today**
- `filter_signal` runs `filter_snooze` first. It runs `filter_dedup` only if no filter action was set.
- **Snooze:** an active snooze filter with an `expiration` still in the future snoozes the instance. If the filter has an expression, the instance must match it. Filters with no expiration are skipped with a warning.
- **Dedup, signal has no filters:** the instance joins the most recent case from an instance of the same signal created within the last **45 minutes** (configurable). The comparison is in minutes, converted to seconds.
- **Dedup, signal has filters:** each active dedup filter looks back `SignalFilter.window` **seconds**. The column default is `60 * 60`, which is 3600 s (1 hour). The pydantic schema default in `models.py:282` is `600`, which is 10 minutes. The instance joins the earliest matching instance's case.

**Inconsistency to note:** the `filter_signal` docstring still says the default window is "1-hour", but the code uses 45 minutes by default.

----- next turn -----

**Cause:** `917a0b7b` (2025-08-14, "share the lookback window computation"). It changed per-filter dedup from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the value as seconds. It did this on the strength of a "stored in seconds" comment. The UI's field is "Window (minutes)" (options 5, 10, 15, 20, 30), so the stored values are minutes. Your filter's `30` became 30 seconds, and two instances ten minutes apart no longer matched.

**Fix**
- `src/dispatch/signal/service.py`: the filter window is now applied as `_window_start(f.window * 60)`, so it means minutes again. Existing filters keep their stored values, so none need editing.
- `src/dispatch/signal/models.py`: the defaults were written in seconds (3600 and 600), which would now mean 60 hours and 10 hours. I changed them to 60 and 10 minutes, the same durations as before. This only affects new filters created without a window.

**Test:** I added `test_filter_actions_deduplicate_window_is_in_minutes`. It uses a filter with `window=30` and an earlier instance ten minutes old that is attached to a case. The new instance must dedup into that case, and it must not dedup once the earlier one is 31 minutes old.
- With the fix, `tests/signal/test_signal_service.py` gives 15 passed, 1 skipped.
- With my source changes stashed, the new test fails and the others pass.

Because of the unit mix-up, filters were effectively deduping over 60 times too short a window since that commit. Instances that were not deduplicated in that period stay in the cases they opened, and I haven't touched that data.

----- next turn -----

**Cause:** `086dc910` (2025-08-07, "simplify snooze filter checks"). I flagged it earlier as a behavior change hidden in a refactor. It changed the expired-filter branch of `filter_snooze` from `continue` to `break`. With the expired filter listed first, the loop stops there and never reaches the valid one, so the instance isn't snoozed.

**Fix:** `src/dispatch/signal/service.py` now uses `continue` again for an expired snooze filter, so the loop keeps checking the remaining filters. The rest of that commit's simplification (merging the mode and action checks) is kept.

**Test:** I added `test_filter_actions_snooze_expired_filter_does_not_hide_valid_one`. It puts a filter that expired 7 days ago before a filter valid for 30 more days, both matching the same entity. The instance must be snoozed.

`tests/signal/test_signal_service.py` now gives 16 passed, 1 skipped. With the source changes stashed, the new test fails along with the dedup-window test from before, and the other 14 pass.

Instances that arrived while this bug was live weren't snoozed, so they may have opened cases or alerts. I haven't touched that data.

----- next turn -----

## Recap

Two regressions came out of the signal refactors from August 2025. Both are fixed in the working tree and not yet committed.

- **Dedup windows:** `917a0b7b` switched a filter's `window` from minutes to seconds, but the UI field is "Window (minutes)". A filter set to 30 therefore deduped over 30 seconds instead of 30 minutes. `filter_dedup` now applies `f.window * 60` seconds. The `SignalFilter.window` column default (3600 to 60) and the schema default (600 to 10) now read as minutes. Existing filters work without being edited.
- **Snoozing:** `086dc910` changed an expired snooze filter from `continue` to `break`. An expired filter listed before a valid one stopped the loop, so the valid snooze was never applied. It is `continue` again.
- **Canary signals:** `a348bbd2` made `filter_dedup` skip canary instances and exclude canary instances as dedup matches. It did not change any window.
- **Default window:** `7a9fe810` replaced the hard-coded 1 hour for signals without filters with a setting. The default is 45 minutes. The `filter_signal` docstring still says "1-hour", which is out of date.
- **Tests:** I added two regression tests in `tests/signal/test_signal_service.py`. Both fail without the fixes. The file's result is 16 passed, 1 skipped.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES