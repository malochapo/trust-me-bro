Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I only read the code and history, and changed nothing. `filter_signal` in `src/dispatch/signal/service.py` runs the snooze check first. It runs the dedup check only if the instance wasn't snoozed.

**1. `a348bbd2` (2025-05-29), "fix(signal): don't dedup on canary signals" (#6026)**
- `filter_dedup` now returns early for a canary instance, so a canary is never deduplicated.
- Existing canary instances are also excluded as dedup matches, both under the default rule and under filter-based rules.
- It changed no time window. The default window was still hard-coded at 1 hour at that point.

**2. `7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
- The default dedup window, used when a signal has no filters, was hard-coded as `timedelta(hours=1)`. It now comes from the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`.
- That setting defaults to **45 minutes**, so the default window shrank from 60 to 45 minutes unless it is overridden.
- The default rule looks for the most recent non-canary instance of the same signal that already has a case and was created within the window. It ignores entities.

**3. `086dc910` (2025-08-07), "simplify snooze filter checks"**
- It merged the mode and action checks into one condition and dropped the "no mode" and "no action" warnings.
- It also changed one behaviour. When an active snooze filter has expired (`expiration <= now`), the loop now does `break` instead of `continue`. An expired snooze filter therefore stops the scan, and any later snooze filters on that signal are no longer checked.
- Snooze uses an expiration timestamp, not a lookback window. A filter with no expiration is skipped with a warning.

**4. `917a0b7b` (2025-08-14), "share the lookback window computation"**
- It added `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
- The default window is now computed as `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds, which is 2700 s (the same 45 minutes).
- Filter-based dedup changed unit. It used `timedelta(minutes=f.window)`; it now treats `f.window` as **seconds**. The model comment and default agree: `SignalFilter.window` defaults to `60 * 60` (3600 s, 1 hour) in `models.py`. The Pydantic schema default is 600, now 10 minutes. Before this commit, a stored value of 3600 was read as 3600 minutes (60 hours), so stored windows were effectively shortened by a factor of 60.

**Windows as the code applies them today**
- **No filters on the signal:** the window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, 45 minutes by default (2700 s).
- **Active dedup filter:** the window is `f.window` in seconds, which defaults to 3600 s in the DB model and 600 s in the schema. The filter takes the earliest matching instance in the window and joins its case.
- **Snooze:** no lookback window; it applies until the filter's `expiration`.

The docstring of `filter_signal` still says the default is a "1-hour window". That is stale, because the default is 45 minutes.

Commits `4474af25` (logging) and `d2675cf4` (redaction) touched the signal flow but did not change snooze or dedup decisions.

----- next turn -----

The commit that broke deduplication windows is `917a0b7b`, "refactor(signal): share the lookback window computation" (2025-08-14). The new test fails on the old code and passes with the fix, and the rest of `tests/signal/test_signal_service.py` still passes.

**Cause.** Before that commit, `filter_dedup` computed the lookback as `timedelta(minutes=f.window)`. The commit moved this into `_window_start(seconds)` and switched it to `timedelta(seconds=...)`. It also added a comment saying the window is "stored in seconds". The filter dialog in the UI (`SignalFilterCreateDialog.vue`) offers the values 5, 10, 15, 20 and 30, labelled "Window (minutes)". So a window of 30 was read as 30 seconds, and two instances ten minutes apart no longer matched.

**Other commits I looked at:**
- `086dc910`: changes the snooze check, not dedup windows. It also swapped `continue` for `break` on an expired snooze filter. I left that alone.
- `7a9fe810`: made the default window configurable.
- `a348bbd2`: stopped deduplicating canary signals.

**Fix.**
- **`src/dispatch/signal/service.py`:** `_window_start` takes minutes again, and the default-window call no longer multiplies by 60. Stored values are already minutes, so existing filters work without editing.
- **`src/dispatch/signal/models.py`:** the `SignalFilter.window` column default was `3600` with a "seconds" comment. It is now `60` with a "minutes" comment, so an unset window means one hour. The schema default went from `600` to `10`. These two defaults would have been read as 3600 and 600 minutes under the corrected code.
- **Regression test:** `test_filter_actions_deduplicate_window_is_in_minutes` uses a filter with `window=30` and an instance created ten minutes earlier. It asserts the new instance is deduplicated.

While writing the test I found that the existing dedup tests do the same `signal.filters.append(SignalFilterFactory(...))` in one expression. In my test that left the signal with no filters, so the default window applied and the test passed on the broken code. Creating the filter first and appending it afterwards works, and my test does that and asserts `signal.filters` is non-empty. I did not touch the existing tests, but they may not be exercising their filters.

The `filter_signal` docstring still says the default window is 1 hour, but the actual default is 45 minutes.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES