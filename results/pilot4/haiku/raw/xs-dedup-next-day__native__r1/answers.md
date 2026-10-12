Four commits since 2025-05-22 changed snooze or dedup behavior or its windows. I did not change any code.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29, "fix(signal): don't dedup on canary signals"): canary signal instances skip deduplication entirely. They are never deduplicated themselves, and canary instances are excluded as match candidates for both the default rule and filter-based rules. No window change.

2. **`7a9fe810`** (2025-06-19, "make the default deduplication window configurable"): the default window for signals with no filters was hard-coded to 1 hour. It now reads `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which is parsed as minutes and defaults to 45.

3. **`086dc910`** (2025-08-07, "simplify snooze filter checks"): the separate mode and action checks, with their warning logs, were merged into one condition. Filters with no mode or action are still skipped, just without a warning. One real behavior change: when a snooze filter's expiration has passed, the loop used to `continue` to the next filter. It now `break`s out, so any later active snooze filters are no longer evaluated for that instance.

4. **`917a0b7b`** (2025-08-14, "share the lookback window computation"): added `_window_start(seconds)`. The default window is now converted to seconds (`minutes * 60`), and the per-filter `SignalFilter.window` is passed in as seconds. Before this, the per-filter window was treated as minutes. This is a behavior change despite the "refactor" title. Any existing filter with a stored window now looks back 60 times less far than before.

**Current values as the code applies them**

- **Snooze:** no lookback window. A snooze filter applies while its `expiration` is in the future. A filter with no expiration is skipped with a warning. A snooze filter with no expression snoozes every instance of that signal.
- **Default dedup (signal has no filters):** 45 minutes, which is 2700 seconds after conversion. It is overridable through the environment variable. It matches any earlier instance of the same signal that has a `case_id` and was created inside the window, regardless of entities.
- **Filter-based dedup:** `SignalFilter.window` is in seconds. The database column defaults to 3600 (1 hour), and the API schema default in `SignalFilterBase` is 600 (10 minutes). Those two defaults disagree.

**Stale comment:** the docstring of `filter_signal` (`src/dispatch/signal/service.py:873`) still says the default rule uses a "1-hour window". The code now uses 45 minutes.

----- next turn -----

The bug came from `917a0b7b` ("refactor(signal): share the lookback window computation", Aug 14 2025). Filter windows are stored and shown in minutes, but that commit started passing `f.window` to a helper that expects seconds. A 30-minute window became 30 seconds, so the two instances ten minutes apart were not grouped. The fix is in place and the signal suite passes (33 passed, 1 skipped).

I couldn't see yesterday's list in this session, so I rebuilt it from `git log` on `src/dispatch/signal/`. The relevant commits are `a348bbd2`, `4474af25`, `7a9fe810`, `086dc910`, `917a0b7b`, and `d2675cf4`.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. Filter windows and the default window both pass minutes. Stored filters need no edits, and the UI and API are unchanged.
- `src/dispatch/signal/models.py`: the column comment now says minutes. I did not change the column default (`60 * 60`) or the API schema default (`600`). Read as minutes, those mean 60 hours and 10 hours, so they may be worth a separate look.
- `docs/docs/administration/settings/signal/filter.mdx` and the `filter_signal` docstring: the default is described as 45 minutes and tied to the setting, instead of "one hour".
- Regression test `test_filter_actions_deduplicate_window_is_minutes` in `tests/signal/test_signal_service.py`: window 30, instances ten minutes apart, expects deduplication. It fails without the fix and passes with it.

**Not fixed: a second regression in `086dc910`**
In `filter_snooze`, the expired-snooze check changed from `continue` to `break`. An expired snooze filter now stops evaluation of any later active snooze filters. This is a snooze bug, not a dedup-window one, so I left it alone. It is a one-word change if you want it.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES