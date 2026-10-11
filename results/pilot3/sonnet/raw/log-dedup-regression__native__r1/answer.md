The root cause is a unit mismatch that a refactor on 2025-08-14 introduced. It shrank every deduplication filter's window from minutes to seconds.

- **The change:** commit `9dc24f46` ("refactor(signal): share the lookback window computation", 2025-08-14) added `_window_start(seconds)`. It replaced `timedelta(minutes=f.window)` in `filter_dedup` with `_window_start(f.window)`, which treats the value as seconds.
- **Units:** the UI labels the filter window "Window (minutes)", and the old code used `minutes=f.window`. The comment the refactor added ("stored in seconds") matches the model comment on `SignalFilter.window` in `src/dispatch/signal/models.py`. But the UI and the previous behaviour both use minutes.
- **Effect:** GuardDuty's filter value of 120 used to mean 2 hours and now means 2 minutes. The log shows these signals arriving roughly every 5–15 minutes, so almost none fall inside the new window. Each one therefore creates a new case.
- **Why other signals look fine:** I did not confirm this against their configuration. The default path for signals with no filter was converted correctly (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`), so those are unaffected. Any other signal that has a dedup filter should be affected the same way.
- **Not checked:** I did not read the log after 2025-08-14 to see the new cases being created. The finding comes from the code diff, the UI label and the arrival pattern in the 08-13 log.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor changed the filter lookback from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the value as seconds, so a 120-minute dedup window became 120 seconds.
INTRODUCED_BY: 9dc24f46