Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I read the diffs and the current code in `src/dispatch/signal/service.py`, `config.py` and `models.py`. Nothing has been changed.

**1. `a348bbd2` (2025-05-29), "fix(signal): don't dedup on canary signals" (#6026)**
- `filter_dedup` now returns early when the incoming instance is a canary, so canaries are never deduplicated.
- Both dedup queries now exclude existing canary instances with `~SignalInstance.canary`.
- This commit does not change any window.
- At the time the default window was still a hard-coded `timedelta(hours=1)`.

**2. `7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
- The default window, used for signals with no filters, changed from the hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- That setting is in `config.py`, is read as an int, and defaults to 45 minutes.
- Signals with no filters therefore now dedup over 45 minutes, not 60, unless the environment variable overrides it. The docstring of `filter_signal` still says "1-hour window", which is out of date.

**3. `086dc910` (2025-08-07), "simplify snooze filter checks"**
- This was presented as a refactor, but it contains one behavior change.
- The refactor merges the mode and action checks into one condition and drops the "no mode" and "no action" warnings.
- The behavior change is in how an expired snooze is handled. `if f.expiration <= now` used to `continue` to the next filter. It now does `break`, which stops checking all remaining filters. A later, unexpired snooze filter on the same signal is no longer evaluated once an expired one is reached.
- Snooze has no window. It depends only on the filter's `expiration` timestamp (UTC), plus an optional entity expression.

**4. `917a0b7b` (2025-08-14), "share the lookback window computation"**
- This was also labelled a refactor. It adds `_window_start(seconds)`, which returns now (UTC) minus `seconds`.
- Default window: it now calls `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`. That is 45 minutes, or 2700 seconds, so the effective value is unchanged.
- Per-filter window: it changed from `timedelta(minutes=f.window)` to `_window_start(f.window)`, so `f.window` is now treated as seconds. This is a behavior change.
  - The `SignalFilter.window` column in `models.py` is documented as seconds, with a default of `60 * 60`, which is 3600 seconds or 1 hour. The Pydantic default at `models.py:282` is 600, which is 10 minutes.
  - With the earlier code, a stored 3600 would have been read as 3600 minutes, or 60 hours. The new code reads it as 1 hour, which matches the column definition.
  - Filters whose stored windows were entered as minutes would now be shortened 60-fold.

**Windows as the code applies them today**

| Case | Window |
|---|---|
| Default dedup, signal has no filters | `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default 45 minutes (computed as ×60 seconds) |
| Dedup with a filter | `SignalFilter.window` in seconds (column default 3600 s; Pydantic default 600 s) |
| Snooze | No lookback window; active until `SignalFilter.expiration` |

Several other commits touched signal code, such as signal stats and `50cf8979` (a 30-day UI limit). They concern stats and display, not the snooze or dedup decision, so I left them out.

----- next turn -----

Commit `917a0b7b` ("share the lookback window computation", 2025-08-14) caused it. The fix and a regression test are in the working tree, uncommitted.

**Cause.** Before that commit, the per-filter lookback was `timedelta(minutes=f.window)`. The commit changed it to `_window_start(f.window)`, which takes seconds, and added the comment "stored in seconds". The UI offers the window in minutes (`Window (minutes)`, with choices 5, 10, 15, 20 and 30), and existing filters store those minute values. So a window of 30 was applied as 30 seconds, and two instances ten minutes apart fell outside it and each opened a case.

**Fix.**
- `src/dispatch/signal/service.py`: the per-filter window is now `_window_start(f.window * 60)`, with a comment saying the value is stored in minutes. Existing filters work without being edited.
- `src/dispatch/signal/models.py`: the `SignalFilter.window` column comment and default were wrong in the same way. The column said "seconds" with a default of `60 * 60`. It now says minutes with a default of `60`, which is still 1 hour. This default only applies when no window is given, and the UI always sends one. It is a Python-side default, so it needs no migration.

**Test.** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py` creates two instances for the same entity ten minutes apart. The filter's window is 30, and the test expects the second instance to be deduplicated into the first one's case. It fails on the old code and passes with the fix. The whole file gives 15 passed and 1 skipped.

I did not touch the Pydantic default of `window` (600) in `models.py`. Read as minutes it would be 10 hours, which looks off, but only the API sees it. Say if you want it changed to 60.

Instances that opened separate cases while the bug was live stay separate, because the fix only affects new instances.

----- next turn -----

The cause is commit `086dc910` ("simplify snooze filter checks", 2025-08-07), which I flagged earlier as a behavior change hidden in a refactor. The fix and a regression test are in the working tree, uncommitted.

**Cause.** In `filter_snooze`, an expired snooze filter used to hit `continue` and move on to the next filter. That commit changed it to `break`, which stops the whole loop. On "Okta: Impossible travel", the expired snooze filter from last week comes first. The loop stops there and never reaches the valid one, so new instances for that user were not snoozed. Any signal where an expired snooze sits ahead of an active one is affected.

**Fix.** In `src/dispatch/signal/service.py`, I changed that `break` back to `continue`. The other `break`s in the function are correct, because they stop after a match has set `filter_action`.

**Test.** `test_filter_actions_snooze_expired_then_active` in `tests/signal/test_signal_service.py` gives a signal two snooze filters on the same entity, listed expired first and then active. It expects the instance to be snoozed. It fails with the old `break` and passes with the fix. The whole file gives 16 passed and 1 skipped.

While I stashed `service.py` to check the new test fails without the fix, I reverted both of today's `service.py` fixes for a moment. I restored them straight away, and `git status` shows `service.py`, `models.py` and the test file as modified.

Instances that were not snoozed while the bug was live stay as they are. The fix only affects new instances.

----- next turn -----

**Recap**

Two regressions came from commits labelled as refactors, and both are now fixed in the working tree. Nothing is committed yet.

- **Deduplication windows.** `917a0b7b` changed the per-filter lookback from minutes to seconds. A filter window of 30, set in minutes in the UI, was applied as 30 seconds, so instances ten minutes apart opened separate cases. The window is now read as minutes again (`f.window * 60`). I also corrected the `SignalFilter.window` column comment and default (now 60 minutes). The regression test is `test_filter_actions_deduplicate_window_is_in_minutes`.
- **Snoozing.** `086dc910` turned `continue` into `break` for expired snooze filters. An expired snooze listed before a valid one stopped the loop, so the valid snooze was never applied. It is now `continue` again. The regression test is `test_filter_actions_snooze_expired_then_active`.
- **Canary signals.** `a348bbd2` made canary instances skip deduplication and excluded existing canary instances from the dedup queries.
- **Default window.** `7a9fe810` made the window for signals without a filter configurable. It was 1 hour and is now 45 minutes by default, and `917a0b7b` left it at 45 minutes. The `filter_signal` docstring still says "1-hour window" and is out of date.

`tests/signal/test_signal_service.py` gives 16 passed and 1 skipped.

DEDUP_WINDOW_BUG: 917a0b7b
SNOOZE_BUG: 086dc910
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES