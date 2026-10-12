Four commits since 2025-05-22 changed how a new signal instance is snoozed or deduplicated. These are all in `src/dispatch/signal/service.py`, and one also touches `src/dispatch/config.py`. I didn't change any code.

**1. `a348bbd2` (2025-05-29), fix(signal): don't dedup on canary signals (#6026)**
- `filter_dedup` now returns right away if the incoming instance is a canary.
- Both dedup queries (the default-window one and the per-filter one) now exclude earlier canary instances with `~SignalInstance.canary`.
- It doesn't change any window.

**2. `7a9fe810` (2025-06-19), feat(signal): make the default deduplication window configurable**
- This applies to signals that have no filters. The window was hard-coded to `timedelta(hours=1)`.
- It now reads `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, which `config.py` defines from an environment variable of the same name. It is cast to `int` and defaults to **45 minutes**.
- The default therefore dropped from 60 to 45 minutes. A deployment that sets the variable gets its own value.

**3. `086dc910` (2025-08-07), refactor(signal): simplify snooze filter checks**
- In `filter_snooze`, the separate "no mode" and "no action" checks, with their warnings, are merged into one condition: `f.mode != active or f.action != snooze`. Missing values still fall through to `continue`, and only the log warnings are lost.
- The behaviour change is in the expiry check. An expired snooze filter used to `continue` to the next filter. It now does `break`, which stops checking all remaining filters.
- A signal with an expired snooze filter listed before a still-valid one will no longer be snoozed by the later filter.
- Snooze expiry is an absolute timestamp (`f.expiration`, compared in UTC). It is not a window.

**4. `917a0b7b` (2025-08-14), refactor(signal): share the lookback window computation**
- It adds a helper, `_window_start(seconds)`, which returns now (UTC) minus that many seconds. Both dedup paths now use it.
- **Default path:** it calls `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`. That is still 45 minutes, now expressed in seconds, so behaviour is unchanged.
- **Per-filter path:** this one is a real change. The code was `timedelta(minutes=f.window)` and is now `_window_start(f.window)`, which treats `f.window` as seconds. The model (`SignalFilter.window`, an Integer) says it is stored in seconds, with a default of `60 * 60`, which is 1 hour. The pydantic schema default is `600`, which is 10 minutes in seconds.
- The old code read that same field as minutes, so a stored 3600 would have meant 3600 minutes, or 60 hours. I couldn't find a commit since 2025-05-22 that changed the model's unit. The old code looks like it was wrong, and this commit fixes it, even though it is labelled a refactor.

**Windows as applied today**

| Case | Value | Unit |
|---|---|---|
| Dedup for signals with no filters | 45 by default (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES`, overridable) | minutes, converted to seconds (×60) |
| Dedup with a filter (`SignalFilter.window`) | 3600 in the model, 600 in the schema | seconds |
| Snooze | `f.expiration` | absolute UTC timestamp |

----- next turn -----

I saved the findings to memory in `signal-snooze-dedup-history.md`, and added a line for it to `MEMORY.md`. The note covers the four commits (`a348bbd2`, `7a9fe810`, `086dc910`, `917a0b7b`), what each changed, and the window values and units as the code applies them today. It also records that the per-filter window changed from minutes to seconds in `917a0b7b`.

I didn't change any code.

----- next turn -----

The commit that broke it is `917a0b7b`, "refactor(signal): share the lookback window computation". It's fixed now, and the new regression test fails without the fix and passes with it. The `tests/signal` suite passes (33 passed, 1 skipped).

**Cause:** the UI offers the window in minutes ("Window (minutes)": 5, 10, 15, 20, 30), and filters were stored in minutes. Before `917a0b7b` the code used `timedelta(minutes=f.window)`. That commit switched it to `_window_start(f.window)`, which reads the value as seconds. A window of 30 therefore meant 30 seconds, which is why the two GuardDuty instances ten minutes apart opened two cases.

**Fix:**
- In `src/dispatch/signal/service.py`, the filter path now calls `_window_start(f.window * 60)`, so the window is minutes again. Existing filters work without being edited because their stored values were always minutes.
- In `src/dispatch/signal/models.py`, I changed the column's Python-side default from `60 * 60` to `60` and corrected its comment to minutes. This only affects new filters. The old default of 3600 only looked like one hour because the unit was assumed to be seconds. Existing rows aren't touched.
- The regression test is `test_filter_actions_deduplicate_window_is_in_minutes` in `tests/signal/test_signal_service.py`. It sets an earlier instance with a case 10 minutes back, a filter with `window=30`, and asserts the new instance is deduplicated into that case.

For the canary question, the commit is `a348bbd2`. It made `filter_dedup` return early for canary instances and excluded canary instances from dedup queries. For signals without a filter, `7a9fe810` replaced the hard-coded 1-hour window with a configurable setting, defaulting to 45 minutes. I re-checked this in the current code.

DEDUP_WINDOW_BUG: 917a0b7b0d2dccbfbd3dfd56b0f4453d8e22d771
CANARY: a348bbd2
DEFAULT_WINDOW: 45 minutes
DEFAULT_WINDOW_SETTING: SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES