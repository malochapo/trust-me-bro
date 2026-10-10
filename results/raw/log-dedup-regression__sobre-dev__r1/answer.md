The cause is a unit mix-up in a refactor. Commit 9dc24f46 (Aug 14, 12:15 -0500) made `filter_dedup` read the filter's `window` as seconds, but it is stored in minutes.

- **Where it shows in the log:** the GuardDuty signal produced cases at a normal rate until Aug 14. From the evening of Aug 14 into Aug 15 it opens new cases minutes apart, for example 48663, 48668, 48672 and 48675 between 21:42 and 22:02. I did not match the 12:15 -0500 commit time against the log's first bad entry.
- **Why only this signal:** it is the one with a deduplication filter set. Signals with no filter use the default-window branch, which the refactor converted correctly. The code only reads `window` for deduplicate filters.
- **What the code did before:** it subtracted `timedelta(minutes=f.window)`, so 120 meant 120 minutes.
- **What the refactor does:** it calls `_window_start(f.window)`, which subtracts `timedelta(seconds=...)`. The new comment "SignalFilter.window is stored in seconds" is wrong. The filter dialog labels the field "Window (minutes)" with choices 5 to 30, so 120 is minutes. 120 now means a 2-minute lookback instead of 2 hours.
- **Effect:** the lookback finds no earlier instance unless one arrived within the last 2 minutes, so each instance opens a new case.
- **Misleading comment on the column:** the `window` column comment in `signal/models.py` says "number of seconds" with a 3600 default. That is probably what misled the refactor, and it contradicts how the UI and the old code used the value.
- **Not verified:** I didn't run the code or check the stored value in the database. The "120 in the UI" figure comes from your report.

Fix: convert with `f.window * 60`, or pass minutes through. Correct the comment and the model note either way.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor treats SignalFilter.window as seconds (`_window_start(f.window)` uses `timedelta(seconds=...)`), but the value is in minutes, so a 120-minute window became 120 seconds and duplicates are no longer found.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef