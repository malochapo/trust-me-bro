Four commits since 2025-05-22 changed the snooze or dedup decision or its windows. I made no code changes.

**Commits**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals (#6026)*
   - `filter_dedup` returns early for canary instances.
   - Canary instances are excluded from the candidate set in both the default-window query and the explicit-filter query.
   - The default window was still a hard-coded 1 hour at this point.

2. **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*
   - The default window (applied when a signal has no filters) moved from hard-coded `timedelta(hours=1)` to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, read in `src/dispatch/config.py`.

3. **`086dc910`** (2025-08-07), *refactor(signal): simplify snooze filter checks*
   - The warning logs for a missing `mode` or `action` were removed. Filters without them still get skipped, so this is a logging-only change.
   - **Behavior change:** when a snooze filter's expiration has passed, the loop went from `continue` to `break`. The first expired active snooze filter now ends the whole loop, so later active snooze filters in the list are never checked for that instance.

4. **`917a0b7b`** (2025-08-14), *refactor(signal): share the lookback window computation*
   - Adds `_window_start(seconds)`.
   - The default window is still 45 minutes, now computed as minutes × 60 seconds.
   - **Behavior change:** the explicit-filter window used to be `timedelta(minutes=f.window)`. It is now `_window_start(f.window)`, which treats the value as seconds. Existing filters now look back 60× less far than before. The commit is titled as a refactor and does not say so. I found no data migration in the history, so stored values were not rescaled.

Other commits I checked and excluded: `4474af25` (logs outcomes only), `d2675cf4` (masks raw fields), `dee1699d` (unrelated), and `5e136d7b` (snooze UI and stats only, no decision logic).

**Current values, as the code applies them**

- **Snooze:** no time window. A snooze applies while `expiration` is in the future. A snooze with no expression matches every instance of the signal. A snooze with an expression matches only instances that satisfy it. Snooze is checked before dedup, and dedup runs only if the instance was not snoozed.
- **Default dedup** (signal has no filters): **45 minutes, which is 2700 seconds**. It comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (int, default 45). It matches earlier instances on the same signal that have a case and are not canary.
- **Explicit dedup filter:** `window` is in **seconds**.
  - The `SignalFilter` column default is 3600 seconds (1 hour).
  - The `SignalFilterBase` default, which applies when a filter is created without a window, is 600 seconds (10 minutes).
  - No commit since 2025-05-22 changed these model defaults.

**Stale documentation:** the `filter_signal` docstring still says the default dedup window is 1 hour. The code uses 45 minutes.

I did not check whether the UI or API labels the window in minutes or seconds. That would confirm whether the `917a0b7b` unit change is actually visible to users.

----- next turn -----

The bug came from `917a0b7b` (refactor(signal): share the lookback window computation, 2025-08-14). The UI and the stored `window` values are in minutes, but that commit started treating `f.window` as seconds. A 30-minute filter became a 30-second lookback, so two instances ten minutes apart didn't group.

Note that I don't have yesterday's list. I rebuilt it from `git log --since=2025-05-22` on the signal modules, and this commit is the one that breaks the window. `7a9fe810` introduced the minutes-based default window but didn't break filter windows.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes, and both the filter window and the default window use it. The `* 60` conversion for the default is gone.
- `src/dispatch/signal/models.py`: the column default is now 60 minutes and the schema default is 10 minutes. Both were in seconds before (3600 and 600).
- No stored filter needs editing. The UI always writes explicit minute values (5–30), so those keep their meaning.

**Regression test**
- `tests/signal/test_signal_service.py::test_filter_actions_deduplicate_window_is_in_minutes`: a 30-minute filter groups an instance from 10 minutes earlier and ignores one from 40 minutes earlier. It fails on the old code and passes now.
- `python -m pytest tests/signal tests/case`: 48 passed, 1 skipped. I did not run the full suite.

**Things to check**
- The docs (`docs/docs/administration/settings/signal/filter.mdx`) still say the default is one hour. I left them alone.
- A filter row created without a window now gets 60 minutes instead of 3600 minutes. That only matters for rows saved without a window, which the UI doesn't do.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES