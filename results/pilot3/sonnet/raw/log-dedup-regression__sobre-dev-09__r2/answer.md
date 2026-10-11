The root cause is a unit mismatch introduced by a refactor on 2025-08-14. The deduplication window is stored in minutes, but the new code reads it as seconds.

- **What the UI stores:** the filter dialog is labelled "Window (minutes)" (`SignalFilterCreateDialog.vue:56`), so a value of 120 means 2 hours. The old code used it that way, with `timedelta(minutes=f.window)`.
- **What the refactor did:** commit `9dc24f46` (2025-08-14 12:15 -0500, "share the lookback window computation") added `_window_start(seconds)` and changed the filter path to `_window_start(f.window)`. It added the comment "SignalFilter.window is stored in seconds", which is wrong, and it matched the stale comment on the model column (`signal/models.py:206`).
- **Effect:** a window of 120 is now a 2-minute lookback. Signal instances arriving more than 2 minutes after the first one no longer find it, so each one opens a new case.
- **Why other signals look fine:** I did not confirm this. My guess is that they have no filters, or have repeats arriving within the shortened window. The no-filter default path passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`, which is still correct.
- **Log evidence:** on 2025-08-13 and early 2025-08-14 the worker log shows GuardDuty instances deduplicating into one case for hours. For example, case 48489 absorbed instances from 02:55 to 04:10 on 2025-08-14. I did not read the log past 2025-08-14 06:56, so I haven't confirmed the new-case-per-instance behaviour there.

The fix is to use `_window_start(f.window * 60)` in the filter loop. The model comment should be corrected too, and the column default of `60 * 60` looks like it was meant as 60 minutes, so check it.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor passes the filter's window, which is stored in minutes, to `_window_start()` as seconds, so a 120-minute window becomes 2 minutes and later duplicates no longer match the open case.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef