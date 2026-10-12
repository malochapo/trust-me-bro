Four commits since 2025-05-22 changed how Dispatch decides whether a new signal instance is snoozed or deduplicated. I haven't changed any code.

**1. `a348bbd2` (2025-05-29), "don't dedup on canary signals" (#6026)**
- `filter_dedup` now returns early for canary instances, so a canary is never deduplicated.
- Both dedup queries now exclude earlier canary instances with `~SignalInstance.canary`, so a canary can't be the case a new signal attaches to.
- This commit has no time window.

**2. `7a9fe810` (2025-06-19), "make the default deduplication window configurable"**
- The default dedup window used when a signal has no filters was hard-coded to `timedelta(hours=1)`. It now comes from a new config value, `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`.
- That value is read from the environment, is an integer in minutes, and defaults to **45 minutes**.
- This reduced the default from 1 hour to 45 minutes.
- The default rule matches any earlier instance of the same signal, created inside the window, that already has a `case_id` and is not a canary. It does not look at entities.

**3. `086dc910` (2025-08-07), "simplify snooze filter checks"**
- The mode and action checks in `filter_snooze` are merged into one condition. The "no mode" and "no action" warnings are removed.
- It also changed behavior: the check for an expired snooze filter went from `continue` to `break`. The loop now stops at the first active snooze filter whose expiration has passed, so later snooze filters on that signal are no longer evaluated.
- The snooze decision has no lookback window. It compares `f.expiration` (treated as UTC) with the current time, and a snooze applies only while `expiration > now`.
- A snooze filter with no expiration is skipped with a warning.
- With an expression, the instance is snoozed only if it matches it. With no expression, it is snoozed regardless of entity.

**4. `917a0b7b` (2025-08-14), "share the lookback window computation"**
- A new `_window_start(seconds)` helper returns now (UTC) minus that many seconds. Both dedup paths use it.
- The default path calls `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, which is 45 minutes (2700 s) unless the environment overrides it. This is the same as before.
- The per-filter path changed units. It was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, so `SignalFilter.window` is treated as **seconds**.
- The model default is `window = 600` (`models.py:282`), which is 10 minutes. The old code would have read that 600 as 600 minutes, or 10 hours.
- A filter-based dedup matches earlier instances that share an entity with the new one and pass the filter expression. It attaches the new instance to the earliest matching instance's case.

**Commits that touched these files but didn't change the decision:**
- `4474af25` only adds logging of the outcome.
- `d2675cf4` adds redaction of sensitive raw fields.

**Stale docstring:** the `filter_signal` docstring still says the default is a "1-hour window". The code applies 45 minutes by default.

----- next turn -----

I saved the task and two findings to the sobre session. Tomorrow, call `sobre_session` with `action="load"` to bring them back.

- **Task:** a read-only investigation of the commits since 2025-05-22 that changed snooze and dedup decisions. It also records that no code has been changed.
- **Finding 1:** the four commits (`a348bbd2`, `7a9fe810`, `086dc910`, `917a0b7b`) and what each changed. It includes the windows as the code applies them today: the default dedup window is 45 minutes, set by `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. The per-filter `window` is in seconds, with a model default of 600 (10 minutes). Snooze uses only an expiration time, not a window.
- **Finding 2:** the `filter_signal` docstring still says the default window is 1 hour. I left it alone because you said not to change code yet.

I didn't write a separate memory file.

----- next turn -----

Commit 917a0b7b ("refactor(signal): share the lookback window computation", 2025-08-14) caused it. It added a `_window_start(seconds)` helper and passed `f.window` to it as seconds. The UI window and the existing stored values are in minutes, so a window of 30 became 30 seconds. Two instances ten minutes apart therefore never grouped.

**Fix**
- **`src/dispatch/signal/service.py`:** `_window_start` now takes minutes. The default-window call no longer multiplies by 60, and the misleading "stored in seconds" comment is corrected. Existing filters work without editing.
- **`src/dispatch/signal/models.py`:** I changed the `SignalFilter.window` column default from 3600 to 60 and fixed its comment. Without this, a new filter that omits the window would have meant 3600 minutes. I did not touch the Pydantic default of 600 on `SignalFilterBase`, and there is no migration.

**Regression test**
- `test_filter_actions_deduplicate_window_is_in_minutes` is in `tests/signal/test_signal_service.py`. It creates an instance that opened a case 10 minutes ago, then checks that a new instance with a 30-minute window is deduplicated into that case.
- It fails without the fix. With the fix, `python -m pytest tests/signal` gives 33 passed and 1 skipped.

I did not run the rest of the suite.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES