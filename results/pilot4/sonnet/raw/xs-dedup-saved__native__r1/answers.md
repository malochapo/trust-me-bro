Five commits since 2025-05-22 touched snooze or dedup. Three of them changed the decision logic or its windows, and two of those three changed which windows apply. The other two, `4474af25` and `086dc910`, change little or nothing about the outcome. I made no code changes.

**Commits that changed the decision or its windows**

- **`a348bbd2` (2025-05-29, #6026), canary signals.**
  - `filter_dedup` now returns early when the new instance is a canary, so canaries are never deduplicated.
  - Both dedup queries (the default one and the per-filter one) also exclude existing canary instances as dedup targets.
  - It changed no window values.
- **`7a9fe810` (2025-06-19), configurable default window.**
  - The default dedup window, used when a signal has no filters, was hard-coded at `timedelta(hours=1)`.
  - It now comes from the new `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` setting in `config.py`, read from the environment as an int.
  - The default for that setting is **45 minutes**, so the default window shrank from 60 to 45 minutes.
- **`917a0b7b` (2025-08-14), shared lookback helper.**
  - It adds `_window_start(seconds)`, which returns now (UTC) minus that many seconds.
  - The default window now calls it as `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`. That is still 45 minutes by default, so no change there.
  - The per-filter window changed from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats `f.window` as **seconds**. The `SignalFilter.window` column is documented as seconds, with a default of 3600 (1 hour). The old code read that value as minutes, so this fixes a unit bug rather than being a pure refactor. A filter with window 3600 was previously looked back 3600 minutes (60 hours) and is now looked back 1 hour.

**Commits with little or no effect on the outcome**

- **`086dc910` (2025-08-07), snooze simplification.**
  - It merges the mode and action checks in `filter_snooze` into one condition (`mode != active or action != snooze`) and drops the "no mode" and "no action" warnings.
  - It also changed an expired snooze filter from `continue` to `break`. When a snooze filter's `expiration` has passed, the loop now stops and skips any later filters, where before it moved on to the next one. That is a real behavior change.
  - Snooze has no lookback window. It depends only on the filter's `expiration` timestamp being in the future.
- **`4474af25` (2025-06-10)** only adds log lines in `flows.py` about the filter outcome and case. It changes no decisions.

**Stale text:** the `filter_signal` docstring in `service.py` still says the default is a "1-hour window", which no longer matches the 45-minute default.

----- next turn -----

I saved the findings to memory as `signal-snooze-dedup-history.md` and added a line for it to `MEMORY.md`. It records the five commits, the window values and units as the code applies them today, and the stale "1-hour" text in the `filter_signal` docstring. It also notes that the findings should be re-checked against the code before anyone relies on them. I changed no code.

----- next turn -----

The breaking commit is `917a0b7b` (2025-08-14, "share the lookback window computation"). The signal tests pass with the fix (33 passed, 1 skipped). The new regression test fails without it.

**Cause:** `SignalFilter.window` holds minutes. The UI field is labelled "Window (minutes)", with choices 5, 10, 15, 20 and 30. Before `917a0b7b` the code used `timedelta(minutes=f.window)`. That commit switched it to seconds, so a window of 30 became 30 seconds. Instances ten minutes apart then fell outside the window and each opened its own case.

My notes from yesterday said that commit "fixed a unit bug" because the column is in seconds. That was wrong: the model comment saying "seconds" was misleading, and the UI and stored data are in minutes.

**Fix:**
- In `src/dispatch/signal/service.py`, the filter window is now `_window_start(f.window * 60)`. Existing filters work as stored, with no edits or migration.
- In `src/dispatch/signal/service.py`, I also corrected the stale "1-hour window" wording in the `filter_signal` docstring to 45 minutes.
- In `src/dispatch/signal/models.py`, I fixed the column comment to say minutes. I also changed the Python-side default from `60 * 60` to `60`, so a new filter defaults to 60 minutes rather than 60 hours. Existing rows are not touched.

**Test:** `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It uses a 30-minute window. An instance 10 minutes old is deduplicated, and one 45 minutes old is not.

The canary commit is `a348bbd2` (#6026), which makes canary signals skip deduplication. The default window for signals without a filter is 45 minutes. `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` in `config.py` changes it.

DEDUP_WINDOW_BUG: 917a0b7b
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES