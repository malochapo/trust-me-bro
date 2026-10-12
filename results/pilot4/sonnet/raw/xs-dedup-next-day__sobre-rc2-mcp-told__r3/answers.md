Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I haven't changed any code. The logic is in `src/dispatch/signal/service.py`, and `filter_snooze` runs first. `filter_dedup` runs only if the instance wasn't snoozed.

**`a348bbd2` (2025-05-29), "fix(signal): don't dedup on canary signals" (#6026)**
- `filter_dedup` now returns right away for a canary instance, so a canary is never deduplicated.
- Existing canary instances are also excluded when looking for a match to dedup against. That applies to both the default rule and filter-based rules.
- It has no time window of its own.

**`7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
- The default dedup rule applies when a signal has no filters. The window was a hardcoded 1 hour, `timedelta(hours=1)`.
- It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, read from the environment as an int and defaulting to **45 minutes**.
- The default therefore dropped from 60 to 45 minutes unless the variable is set.

**`086dc910` (2025-08-07), "simplify snooze filter checks"**
- It collapses the separate "no mode" and "no action" checks, with their warning logs, into one condition. A filter is skipped unless its mode is active and its action is snooze.
- This one is not a pure refactor. When a snooze filter's expiration has already passed, the loop used to `continue` to the next filter. It now does `break`, so any later snooze filters on that signal are no longer checked.
- Snooze uses an absolute `expiration` timestamp compared against the current UTC time, not a window.

**`917a0b7b` (2025-08-14), "share the lookback window computation"**
- It adds the helper `_window_start(seconds)`, which returns the current UTC time minus that many seconds.
- Default rule: the window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, which is 2700 s (45 minutes) by default. This matches the old behaviour.
- Filter-based rule: the window is `SignalFilter.window` passed as **seconds**. Before this commit it was `timedelta(minutes=f.window)`. The model column in `src/dispatch/signal/models.py:206` defaults to 3600 s (1 hour) and is commented as seconds. The Pydantic schema default is `window: int | None = 600`, which is 10 minutes.
- Because of that change, stored filter windows are now interpreted as seconds where they were interpreted as minutes before.
- The UI dialog `SignalFilterCreateDialog.vue` still labels the field "Window (minutes)". Values entered there are now applied as seconds, which is likely a bug. I haven't checked the UI's selectable values or how they are saved.

Other signal commits in this period did not change snooze or dedup decisions, for example `5e136d7b` (UI views) and `d2675cf4` (masking raw fields).

----- next turn -----

Commit 917a0b7b ("share the lookback window computation") caused the bug. It added `_window_start(seconds)` and passed `f.window` into it, with a comment saying `SignalFilter.window` is stored in seconds. The UI's filter dialog labels the field "Window (minutes)", and the old code used `timedelta(minutes=f.window)`. After the commit, a window of 30 meant 30 seconds, so two instances ten minutes apart no longer deduplicated.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes, and filters pass `f.window` straight through. The default no-filter window also passes minutes, without the `* 60`. Stored values were already minutes, so existing filters work without being edited.
- `src/dispatch/signal/models.py`: I fixed the column and schema defaults, which were written in seconds (3600 and 600). They are now 60 and 10 minutes. The schema default is the one a filter created through the API without a window would get; at 600 it would have meant 10 hours.

**Regression test**
- `test_filter_dedup_window_is_in_minutes` has a 30-minute window and an instance 10 minutes old, and expects the new instance to join its case.
- It fails on the old code and passes with the fix.
- `tests/signal` passes: 33 passed, 1 skipped.

The `NN` in the default window below is from `7a9fe810`, which made the default window configurable. The canary commit is `a348bbd2`.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES