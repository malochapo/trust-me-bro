The cause is a unit change in the deduplication window. Commit 9dc24f46 (2025-08-14 12:15, "share the lookback window computation") introduced it.

- **Before:** `filter_dedup` computed the filter window as `timedelta(minutes=f.window)`. A window of 120 meant 120 minutes.
- **After:** the refactor routes it through the new helper `_window_start(seconds)`, with the comment "SignalFilter.window is stored in seconds". `filter_dedup` (`src/dispatch/signal/service.py:846`) now passes `f.window` unchanged, so 120 becomes 120 seconds.
- **Why it hits only this signal:** a GuardDuty instance older than 2 minutes no longer matches an open case, so each new instance opens its own case. Signals that arrive within a couple of minutes of each other still dedupe. The default-window path has no filters and was converted correctly with `* 60`.
- **Timing:** the commit date matches the report. I didn't confirm that the 2025-08-14 case-per-instance burst in the log lines up with the deploy of this commit.

I didn't run any tests or change anything. The fix is to pass `f.window * 60` (or `f.window` in minutes) to `_window_start`.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor treats the filter's window value (stored in minutes, e.g. 120) as seconds, so the dedup lookback shrinks from 120 minutes to 120 seconds and new signals no longer match the open case.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef