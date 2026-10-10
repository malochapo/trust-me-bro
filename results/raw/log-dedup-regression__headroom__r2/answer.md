The root cause is commit 9dc24f46, a refactor on 2025-08-14 that changed the unit of the deduplication window from minutes to seconds.

- **Unit change:** `SignalFilter.window` is entered in minutes ("Window (minutes)" in the filter dialog) and the old code used `timedelta(minutes=f.window)`. The refactor added a `_window_start(seconds)` helper and switched `filter_dedup` to `_window_start(f.window)`, so the stored value is now read as seconds. The comment on the model column says seconds, which is probably what misled the author. The comment disagrees with the UI and with the original code.
- **Effect on this signal:** the window of 120 that used to mean 2 hours now means 2 minutes. A repeat GuardDuty signal that arrives more than 2 minutes after the first one no longer finds a match, so it opens a new case.
- **Why only this signal:** the default path, for signals with no filter, multiplies by 60 before calling the helper, so it is unaffected. Only signals with an explicit dedup filter hit the changed line.
- **Log evidence:** GuardDuty dedups into case 48393 on 2025-08-13 and into 48593 on 2025-08-14 at 14:27Z. The same signal creates cases (48839 on 2025-08-15, for example) on the 15th. I sampled the log rather than reading all 6,741 lines, and I didn't confirm the exact time the behaviour flipped.
- **Not verified:** I didn't run the code or check that the 2025-08-14 deploy time lines up with the first new case. I only compared the diff against the UI label and the original code.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor passes `f.window` (stored in minutes, per the UI and the original `timedelta(minutes=f.window)`) to the new `_window_start(seconds)` helper, so a 120-minute dedup window is treated as 120 seconds and repeat signals no longer match the open case.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef