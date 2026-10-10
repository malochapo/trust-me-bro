The root cause is a units bug in commit `9dc24f46`, "refactor(signal): share the lookback window computation". It was committed on 2025-08-14 at 12:15 -0500, which matches the start of the problem.

- **Before:** the per-filter dedup code used `timedelta(minutes=f.window)`. A window of 120 meant 120 minutes.
- **After:** the refactor added `_window_start(seconds)` and changed the filter path to `_window_start(f.window)`. It also added a comment claiming `SignalFilter.window` "is stored in seconds", but the old code read it as minutes.
- **Effect:** the 120 in the UI is now read as 120 seconds, so the lookback is about 2 minutes. Repeat GuardDuty alerts usually arrive further apart than that, so they no longer find the open case and each one opens a new case.
- **Why only this signal:** the default-window branch (signals with no filters) was converted correctly, using `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`. So signals without a custom dedup filter are unaffected.

The log shows GuardDuty alerts deduplicating normally on 2025-08-13, including a 14:00 UTC-style gap of 10+ minutes between instances. I did not trace the post-deploy GuardDuty entries in the log, and I did not confirm the unit in the UI code. I inferred "minutes" from the old code and the UI value.

The fix is to change the call in `filter_dedup` to `_window_start(f.window * 60)` and delete the incorrect comment.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor passes the filter's window, which is stored in minutes, to the new `_window_start(seconds)` helper as if it were seconds, so a 120-minute window shrinks to 120 seconds and repeat alerts no longer match the open case.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef