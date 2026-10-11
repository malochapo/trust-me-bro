Four commits since 2025-05-22 changed the snooze/dedup decision or its windows. The most important is `917a0b7b`, which silently changed the filter window from minutes to seconds. I made no code changes.

## Commits

1. **`a348bbd2`** (2025-05-29) *fix(signal): don't dedup on canary signals (#6026)*
   - `filter_dedup` returns early for canary signals, and canary instances are excluded from dedup lookups in both the default and filter-based paths.
   - Snooze is unaffected.

2. **`7a9fe810`** (2025-06-19) *feat(signal): make the default deduplication window configurable*
   - The default window for signals with no dedup filter was hard-coded at 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py:95`), defaulting to 45.
   - The `filter_signal` docstring still says "1-hour window", which is now stale.

3. **`086dc910`** (2025-08-07) *refactor(signal): simplify snooze filter checks*
   - Merged the mode and action checks into one condition and dropped the "no mode" / "no action" warning logs. The skip behavior is the same, since `None != active` already continues.
   - **Behavior change:** when a snooze filter's expiration has passed, the code now `break`s instead of `continue`s. Any later snooze filters in the list are no longer evaluated. The commit is labeled as a refactor.

4. **`917a0b7b`** (2025-08-14) *refactor(signal): share the lookback window computation*
   - Added `_window_start(seconds)`. The default dedup path now calls it with `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`, so the default is still 45 minutes.
   - **Behavior change:** the filter window used to be `timedelta(minutes=f.window)`. It is now `_window_start(f.window)`, which treats `f.window` as seconds. Any existing filter's window is now 60× shorter than before. No migration appears in this commit.

## Current values as the code applies them

- **Default dedup window** (signal has no filters): 45 min = 2700 s. It looks back from `created_at` and matches an existing instance with a `case_id`, on the same signal, and not canary.
- **Filter dedup window** (`SignalFilter.window`): seconds.
  - Model column default is 3600 s (1 hour), in `src/dispatch/signal/models.py:206-208`.
  - API schema default is 600 s (10 min), in `models.py:282`.
- **Snooze**: no time window. It only checks `expiration` against now.
- **Not a dedup or snooze window:** `flows.py:373` has `timedelta(seconds=5)`, a throttle on Slack thread updates. It is unchanged since 2025-05-22.

## Problem to fix

The UI still says "Window (minutes)" and offers 5, 10, 15, 20, 30 (`src/dispatch/static/dispatch/src/signal/filter/SignalFilterCreateDialog.vue:56,196`). It sends the raw value without converting it. A user who picks 30 minutes now gets a 30-second dedup window. The `917a0b7b` change needs to be reverted, or the UI and existing data need converting to seconds.

I did not check the tests or the database for existing filter rows, and I did not verify whether a `null` window from the UI store would reach `_window_start` and fail.

----- next turn -----

**Cause:** `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed the filter window from `timedelta(minutes=f.window)` to seconds. A window of 30 became 30 seconds, so two instances ten minutes apart never matched. The earlier commit `7a9fe810` only changed the default window, which is not what hit this filter.

**Fix** (uncommitted):
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again. Both the filter window and `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` use it directly. The stale "1-hour window" docstring now names the config setting.
- `src/dispatch/signal/models.py`: the `window` column comment now says minutes.
- Existing filters need no edits. The UI already stores minutes, and the stored values are read as minutes again.

**Regression test:** `test_filter_actions_deduplicate_window_is_minutes` in `tests/signal/test_signal_service.py`. It creates an instance ten minutes old and checks that a 30-minute window groups it, while a 5-minute window does not. It fails on the old code and passes on the fix.

**Tests:** `python -m pytest tests/signal` gives 34 passed, 1 skipped (the skip was already there). I did not run the full suite.

**Not changed, for you to decide:**
- The `SignalFilter.window` column default is `60 * 60` (now 3600 minutes, about 60 hours). The API schema default is `600` (600 minutes). Both were already read as minutes before `917a0b7b`, so I kept them to avoid changing behavior for filters created without a window. The intended value is probably 60 and 600 minutes respectively.
- `086dc910` changed the expired-snooze branch from `continue` to `break`, so an expired snooze filter now stops evaluation of the remaining filters. I didn't change this, since it isn't part of the reported problem.
- I did not check whether a `null` window from the UI would reach `_window_start`.

----- next turn -----

The cause was `086dc910`, the commit that changed the expired-snooze branch to `break`. The loop stopped at the expired filter, so the valid filter after it was never checked. New instances for that user were not snoozed.

**Fix** (uncommitted): in `filter_snooze` (`src/dispatch/signal/service.py`), the expired-expiration branch now does `continue` instead of `break`. Expired filters are skipped, and the loop keeps checking the rest.

**Regression test:** `test_filter_actions_snooze_expired_before_active` in `tests/signal/test_signal_service.py`. It puts the expired filter first and the valid one second, then checks that the instance is snoozed. Temporarily restoring `break` makes it fail, and the fix makes it pass.

**Tests:** `python -m pytest tests/signal` gives 35 passed, 1 skipped (the skip was already there). Ruff passes on the signal source and tests. I did not run the full suite.

The three changes from this session are still uncommitted in the working tree: the minutes fix for the dedup window, its regression test, and this snooze fix.

----- next turn -----

## Recap

Three commits since 2025-05-22 caused or changed the reported behavior:

- **`917a0b7b`** changed the filter dedup window from minutes to seconds. A 30-minute window became 30 seconds, so instances ten minutes apart opened separate cases. The fix treats the window as minutes again, which is what the UI sends and what existing filters store. The model comment now says minutes.
- **`086dc910`** changed the expired-snooze branch from `continue` to `break`. An expired snooze filter ahead of a valid one stopped the loop, so new instances were not snoozed. The fix restores `continue`.
- **`a348bbd2`** made filter dedup skip canary signals, and excluded canary instances from dedup lookups.

Regression tests were added for the window units and the expired-before-active snooze case. I did not run the full suite. The signal tests pass (35 passed, 1 skipped, where the skip predates this work). These changes are uncommitted in the working tree.

Open items, not changed:
- The `SignalFilter.window` column default (3600) and the API default (600) are read as minutes, which makes them 60 hours and 10 hours. The intended values are probably 60 and 600 minutes.
- Whether a `null` window from the UI could reach the dedup query is unverified.

```
DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES
```