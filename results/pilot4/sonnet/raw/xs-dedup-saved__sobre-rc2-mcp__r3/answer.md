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