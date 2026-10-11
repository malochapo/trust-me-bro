The root cause is a unit error in a refactor. `filter_dedup` in `src/dispatch/signal/service.py` now treats `SignalFilter.window` as seconds, but the value is stored in minutes.

The old code used `timedelta(minutes=f.window)`. Commit 9dc24f46 (2025-08-14) added a shared helper, `_window_start(seconds)`, and changed the filter branch to `_window_start(f.window)`. A window of 120 now means 120 seconds instead of 120 minutes. The comment "SignalFilter.window is stored in seconds" is wrong.

The default-window branch was converted correctly (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`), so only signals with an explicit dedup filter are affected. That fits "other signals look fine", which presumably have no dedup filter.

I did not confirm in `models.py` that the window is stored in minutes. The old code and the "120 in the UI" report both point that way.

The log shows GuardDuty instances deduplicating into existing cases on 2025-08-13, with gaps of 5 to 15 minutes between instances. A 120-second window would no longer match those gaps, so each instance opens a new case.

The fix is to pass `f.window * 60` in the filter branch.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor passes the filter's window (stored in minutes) to `_window_start()` as seconds, so a 120-minute dedup window shrinks to 120 seconds and instances stop matching the open case.
INTRODUCED_BY: 9dc24f46