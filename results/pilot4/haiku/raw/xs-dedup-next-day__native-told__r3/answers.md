Four commits since 2025-05-22 changed how Dispatch decides snooze or dedup for a new signal instance. No code was changed.

**Commits (oldest first)**

1. **`a348bbd2`** (2025-05-29), *fix(signal): don't dedup on canary signals*. Canary instances are skipped in `filter_dedup` and excluded from the dedup queries.
2. **`7a9fe810`** (2025-06-19), *make the default deduplication window configurable*. Adds `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `src/dispatch/config.py`, default 45, applied as minutes.
3. **`086dc910`** (2025-08-07), *refactor(signal): simplify snooze filter checks*. Merges the mode and action checks into one. It also changes an expired snooze from `continue` to `break`, so later snooze filters on the signal are no longer evaluated once one has expired. The commit message does not mention this behaviour change.
4. **`917a0b7b`** (2025-08-14), *refactor(signal): share the lookback window computation*. Adds `_window_start(seconds)` and removes `timedelta(minutes=f.window)`, so `SignalFilter.window` is now read as **seconds**. This is a unit change inside a commit labelled as a refactor.

**Windows as the code applies them today**

- **Default dedup (signal has no filters):** 45 minutes, i.e. 2700 seconds (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`).
- **Filter dedup (`action=deduplicate`):** `f.window` in seconds. The model default is 3600 seconds. The `SignalFilterBase` schema default is 600 seconds.
- **Snooze:** no time window. It is governed by `expiration`.

**Things to check**

- The UI dialog `src/dispatch/static/dispatch/src/signal/filter/SignalFilterCreateDialog.vue` labels the window "Window (minutes)" with options 5, 10, 15, 20, 30. Those values are sent as-is and now interpreted as seconds, so a "10 minute" choice becomes a 10-second window. This is probably the most important finding.
- The `filter_signal` docstring still says the default dedup is a 1-hour window, but the code uses 45 minutes.
- Tests in `tests/signal/test_signal_service.py` use `window=5`, which is 5 seconds under the current code.

I also saved these findings to the project memory directory so a later session can pick them up.

----- next turn -----

The commit that broke deduplication windows is **917a0b7b** (2025-08-14, "refactor(signal): share the lookback window computation"). It replaced `timedelta(minutes=f.window)` with a seconds-based helper, so a filter window of 30 became 30 seconds. Your two instances ten minutes apart fell outside that window and opened two cases.

**The fix**
- `src/dispatch/signal/service.py`: `_window_start` takes minutes again, and both the filter window and the default window use minutes. The `filter_signal` docstring no longer claims a fixed 1-hour default.
- `src/dispatch/signal/models.py`: the `SignalFilter.window` column default is 60 minutes (was 3600 "seconds"), and the schema default is 10 minutes (was 600). This is the same effective behaviour as before the bug, just in the correct unit.
- No migration: stored filters already hold minute values (for example 30 from the UI), so they start working as intended without being edited.

**Regression test**
- `tests/signal/test_signal_service.py::test_filter_actions_deduplicate_window_is_minutes` uses a 30-minute deduplicate filter. An instance 10 minutes old groups with the new one; one 40 minutes old does not. The 10-minute case failed on the old code and passes now.
- `python -m pytest tests/signal` gives 34 passed, 1 skipped. The skip was already there.

**Other things I checked**
- The canary commit is **a348bbd2**. It made `filter_dedup` return early for canary instances and excluded canary instances from dedup queries. The current code still does this.
- Commit 086dc910 changed `continue` to `break` in snooze handling. That affects snooze, not window units, so it is not the cause here.
- The UI dialog (`SignalFilterCreateDialog.vue`) already labels the window in minutes, so no UI change was needed.
- I did not commit. The changes are in the working tree.
- Black reports a pre-existing formatting issue at `models.py:411`, which I left alone.

I also updated the memory note on this history, since it said windows were seconds.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES