Since 2025-05-22, four commits changed the snooze/dedup decision or its windows. All of them touch `src/dispatch/signal/service.py`, and I haven't changed any code.

**Commits**

1. **`a348bbd2`** (2025-05-29, fix(signal): don't dedup on canary signals). Canary signal instances skip deduplication. The default-window query and the per-filter query both exclude canary instances, so canaries are neither deduplicated nor used as matches.

2. **`7a9fe810`** (2025-06-19, feat(signal): make the default deduplication window configurable). The default dedup window for signals with no dedup filter moved from a hard-coded 1 hour to `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`src/dispatch/config.py`), which defaults to 45 minutes. The value is read as minutes, and the code converts it to seconds.

3. **`086dc910`** (2025-08-07, refactor(signal): simplify snooze filter checks). The title says refactor, but it changes behavior in `filter_snooze`. The mode/action checks are merged into one condition, and the log warnings for missing mode or action are gone. More importantly, an expired snooze filter now hits `break` instead of `continue`. Evaluation stops there, so any later active snooze filters on the same signal are no longer checked.

4. **`917a0b7b`** (2025-08-14, refactor(signal): share the lookback window computation). This adds `_window_start(seconds)`. The default dedup path now converts minutes to seconds before calling it. The per-filter path now passes `f.window` as seconds. Before this commit it was `timedelta(minutes=f.window)`, so this changes existing filters' effective window from minutes to seconds. For example, a stored `window=600` used to mean 10 hours and now means 10 minutes. I found no migration that rescales stored values. This is a behavior change under a refactor title.

**Windows as the code applies them today**

- **Snooze:** there is no lookback window. A snooze lasts until the filter's `expiration` datetime. A snooze filter with no expiration is skipped with a warning, and one with an expression only applies if the instance matches it.
- **Default dedup (signal has no filters):** `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, default **45 minutes**, with an environment override. Converted to seconds before the query.
- **Per-filter dedup:** `SignalFilter.window`, in **seconds**. The database column defaults to **3600 s (1 hour)**. The API model `SignalFilterBase` defaults to **600 s (10 minutes)** when the client omits it. The column comment still says "default to 1 hour", which matches the column but not the API default.

Snooze is checked first. Deduplication runs only if no snooze matched.

**Stale text:** the `filter_dedup`-related docstring in `process_signal_instance` (around `service.py:873`) still says the default dedup window is 1 hour.

----- next turn -----

The bug came from commit `917a0b7b` ("refactor(signal): share the lookback window computation"). It changed the filter window from minutes to seconds, so a window of 30 now means 30 seconds. Your two GuardDuty instances ten minutes apart fall outside that and open two cases.

One caveat: I don't have the earlier list from yesterday in this conversation. I rebuilt it from `git log` since 2025-05-22, filtering for signal snooze and dedup changes.

**Cause**
- The UI labels the field "Window (minutes)" and offers 5–30 (`SignalFilterCreateDialog.vue`). The value is stored unchanged.
- Before `917a0b7b`, the code read it as minutes (`timedelta(minutes=f.window)`).
- `917a0b7b` changed that to seconds, based on a comment in the model that dates from 2023. Existing filters now shrink from 30 minutes to 30 seconds.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again, and both the filter window and the default window call it with minutes. The filter comment now says minutes.
- `src/dispatch/signal/models.py`: the column default is 60 minutes (it was 3600, which would now read as 60 hours). The comment says minutes. No migration is needed, and stored values are untouched.
- `tests/signal/test_signal_service.py`: added `test_filter_dedup_window_is_in_minutes`. It has a 30-minute filter, one instance 10 minutes old that should match, and one 40 minutes old that should not.

**Verification**
- `python -m pytest tests/signal`: 33 passed, 1 skipped.
- The new test fails with the fix stashed and passes with it.
- `ruff` isn't installed here, so I checked line length by hand against the 100-character limit.

**Canary**
- `a348bbd2` ("fix(signal): don't dedup on canary signals") is the commit that changed canary dedup. It skips canary instances as both the deduplicating instance and the match.

**Default window**
- Signals with no filter use a 45-minute window, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` (`config.py`). `7a9fe810` made it configurable.
- The docstring of `filter_signal` still says 1 hour. I left it alone.

**Found but not changed** (outside the window fix)
- `086dc910` changed `continue` to `break` for expired snooze filters in `filter_snooze`. Now an expired snooze filter stops evaluation, so any active snooze filter later in the list is skipped. This is a real snooze regression and needs its own fix.
- `SignalFilterBase.window` defaults to 600 in the API schema. Under the minutes meaning that is 10 hours. I left it, since changing it alters what API calls without a window create.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES