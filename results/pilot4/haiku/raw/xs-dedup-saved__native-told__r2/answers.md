Four commits since 2025-05-22 changed snooze or dedup logic in `src/dispatch/signal/service.py`. None of them changed the snooze window, because snoozes have no window; they only use an expiration timestamp. I did not change any code.

**Commits, oldest first**

1. **`a348bbd2`** (2025-05-29), "fix(signal): don't dedup on canary signals". Canary instances skip dedup entirely. Canary instances are also excluded as dedup matches, in both the default and filter-based paths. No window values changed.

2. **`7a9fe810`** (2025-06-19), "make the default deduplication window configurable". The default window for signals with no dedup filter was hard-coded at 1 hour. It now comes from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py`, which defaults to 45 minutes.

3. **`086dc910`** (2025-08-07), "simplify snooze filter checks". Snooze filters with an expired expiration now `break` out of the loop instead of `continue`. Later active snooze filters on the same signal are no longer evaluated after an expired one. The warnings for a missing mode or action were also dropped, but those filters are still skipped.

4. **`917a0b7b`** (2025-08-14), "share the lookback window computation". This added `_window_start()`. The default dedup window is now `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds. The per-filter dedup window changed from `timedelta(minutes=f.window)` to `_window_start(f.window)`, so `SignalFilter.window` is now read as seconds. Stored values were not migrated, so an existing filter with `window=10` now looks back 10 seconds instead of 10 minutes.

**Current values and units**

- **Default dedup (no dedup filter on the signal):** 45 minutes (2700 seconds), unless `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` is set.
- **Filter dedup window (`SignalFilter.window`):** seconds. The model column defaults to 3600 (1 hour). The API schema `SignalFilterBase` defaults to 600 (10 minutes).
- **Snooze:** no window. Only `expiration` applies.

**Things to check**

- The UI mismatch is the most important one. `SignalFilterCreateDialog.vue` labels the field "Window (minutes)" and offers 5, 10, 15, 20, 30. It does not convert to seconds, so a user who picks 10 gets a 10-second lookback.
- The `filter_signal` docstring still says the default dedup is a 1-hour window, which is stale.

I also saved this history to the memory directory for later sessions.

----- next turn -----

I saved the findings to the existing memory file, `signal-snooze-dedup-windows.md`, and its index line in `MEMORY.md` is already there. A new session can pick them up from there.

The file now records:
- The four commits since 2025-05-22 that changed snooze or dedup logic: `a348bbd2`, `7a9fe810`, `086dc910`, and `917a0b7b`.
- The current windows and units. The default dedup window is 45 minutes, from `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`. The per-filter dedup window is read as seconds, with a model default of 3600 and an API default of 600. Snooze has no window, only an expiration.
- The order in `filter_signal`: snooze runs first, and dedup runs only if the instance was not snoozed.
- Two open issues, neither fixed. The UI labels the filter window in minutes (5–30) but the backend reads seconds, so a "10" gives a 10-second lookback. The `filter_signal` docstring still says the default dedup is 1 hour.

No code was changed in this session. The next step for tomorrow is to decide which side of the unit mismatch to fix.

----- next turn -----

The cause is commit `917a0b7b` (2025-08-14, "refactor(signal): share the lookback window computation"). It changed `SignalFilter.window` from minutes to seconds without migrating stored data or updating the UI. A 30-minute filter therefore looked back 30 seconds, so two instances ten minutes apart opened two cases.

**Fix**
- `src/dispatch/signal/service.py`: `_window_start` now takes minutes, and both the per-filter window and the default dedup window use it. The default window is `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` seconds before this change and is now passed directly as minutes. The `filter_signal` docstring now refers to the setting instead of "1-hour window".
- `src/dispatch/signal/models.py`: the `window` column default is now `60` minutes (was `3600`, which was seconds). This is a Python-side default, so no migration is needed.
- Existing filters need no edits. Their stored values (5–30, as entered in the UI) were already minutes before the regression, and the UI label stays as it is.

**Regression tests** in `tests/signal/test_signal_service.py`:
- `test_filter_window_is_in_minutes`: a 30-minute filter groups an instance from ten minutes earlier. It fails on the old code and passes with the fix.
- `test_filter_window_excludes_instances_outside_window`: a 5-minute filter does not group that same instance.

`python -m pytest tests/signal tests/case tests/plugins/dispatch_slack` gives 58 passed and 1 skipped.

I left the Pydantic `SignalFilterBase.window` default at 600. It is now 600 minutes (10 hours) for API calls that omit `window`, which matches the pre-regression behaviour. Say if you want it changed.

The changes are uncommitted. I also updated the memory note for this topic.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES