Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. All are in `src/dispatch/signal/service.py`, and one also touched `src/dispatch/config.py`. I read the diffs and the current code. I didn't run anything or change any code.

1. **`a348bbd2` (2025-05-29), "don't dedup on canary signals (#6026)"**
   - `filter_dedup` now returns right away for canary instances.
   - Both dedup queries, the default one and the per-filter one, now exclude canary instances (`~SignalInstance.canary`) from the candidates.
   - It adds no time window.

2. **`7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
   - The default window applies to signals that have no filters. It was hard-coded to `timedelta(hours=1)`.
   - It is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, a new setting in `config.py` that defaults to **45 minutes**, so the default behaviour dropped from 60 to 45 minutes.
   - The `filter_signal` docstring still says "1-hour window", which is now stale.

3. **`086dc910` (2025-08-07), "simplify snooze filter checks"**
   - It folds the separate mode and action checks into one condition: `f.mode != active or f.action != snooze`. This also removes the "no mode" and "no action" warnings.
   - It changes one behaviour: an expired snooze filter now does `break` instead of `continue`. The loop stops at the first expired snooze filter, so later snooze filters on that signal are not checked.
   - It adds no window. The snooze check compares `f.expiration` (treated as UTC) with the current time, and filters with no expiration are skipped with a warning.

4. **`917a0b7b` (2025-08-14), "share the lookback window computation"**
   - It adds `_window_start(seconds)`, which returns now (UTC) minus `seconds`.
   - The default dedup window is now `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, which is 45 × 60 = **2700 seconds**. That is the same 45 minutes as before.
   - The per-filter window changed. It was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, with a new comment saying `SignalFilter.window` is stored in seconds. So `f.window` is now read as **seconds**.
   - This commit is labelled a refactor, but it changes behaviour for filters with a dedup window.

**The per-filter window may now be misread.** `SignalFilter.window` in `models.py` defaults to `60 * 60`, and its comment says that is seconds (1 hour). The pydantic model default is `600`.

But the filter dialog (`SignalFilterCreateDialog.vue`) is labelled "Window (minutes)" and offers `[5, 10, 15, 20, 30]`. If the UI saves those numbers unchanged, a "5" is now treated as 5 seconds instead of 5 minutes. I only looked at the dialog, not at how the value is saved or converted. That is worth checking.

**Current values as the code applies them**
- Default dedup window (signal has no filters): 45 minutes by default, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` and applied as 2700 seconds.
- Per-filter dedup window: `f.window`, in seconds. The model default is 3600 s (1 hour).
- Snooze: not a lookback window. It applies until the filter's `expiration` timestamp.

----- next turn -----

The bug came from commit 917a0b7b ("refactor(signal): share the lookback window computation", 2025-08-14). The new test fails without the fix and passes with it, and `python -m pytest tests/signal` passes (33 passed, 1 skipped). I didn't run the full test suite.

**Cause.** Before that commit, the filter lookback was `timedelta(minutes=f.window)`. The commit added a `_window_start(seconds)` helper and passed `f.window` through it as seconds, with a comment saying the window is stored in seconds. But the UI labels the field "Window (minutes)" and offers 5/10/15/20/30. Existing rows therefore hold minutes. A window of 30 became 30 seconds, so two instances ten minutes apart no longer grouped into one case.

**Fix.**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes. The filter path passes `f.window` as minutes, and the default path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` without the `* 60`. Existing filters work without being edited.
- `src/dispatch/signal/models.py`: I corrected the column comment, which wrongly said seconds.
- Regression test: `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It uses a window of 30 and two instances ten minutes apart, and checks that they deduplicate into the same case.

I left the column default (`60 * 60`) and the schema default (`600`) alone. Read as minutes, both are odd values, but the UI always sets a window, so I didn't change them.

The canary commit is a348bbd2 (2025-05-29, "don't dedup on canary signals"). The default-window setting was introduced in 7a9fe810. The default window is 45 minutes unless the setting is overridden; the code default is 45, although the `filter_signal` docstring still says 1 hour.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES