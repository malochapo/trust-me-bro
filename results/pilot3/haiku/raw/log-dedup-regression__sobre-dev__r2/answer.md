**Root cause:** commit `9dc24f46` changed how `filter_dedup` reads a deduplicate filter's window. The window used to be applied as minutes; it is now applied as seconds. The UI value of 120 therefore went from a 2-hour lookback to a 2-minute lookback, so any GuardDuty instance arriving more than about 2 minutes after the previous one no longer finds the open case and creates a new one.

The old line was `window = datetime.now(timezone.utc) - timedelta(minutes=f.window)`. The new line is `window = _window_start(f.window)`, which treats `f.window` as seconds. The `SignalFilter.window` column comment in `models.py` already says seconds, so the code and the model disagreed before this commit, and the commit silently picked the seconds reading.

This explains "other signals look fine": signals without a custom deduplicate filter use the separate default-window branch (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`), which this commit did not touch.

**Caveats on the evidence:**
- The log timing doesn't line up neatly with the commit. The commit is timestamped 2025-08-14 17:15 UTC, but the log shows the first GuardDuty case creation on 2025-08-14 at 02:55 UTC. Dedup keeps working in the log with gaps of up to about 12 minutes until about 21:40 UTC, and then new-case creation dominates from about 21:42 UTC onward. The timestamps may be in a different timezone or the commit may have been deployed later than it was committed. Either way, the code path is the only one that matches "custom dedup filter with window 120 breaks, default-window signals are fine."
- I could not confirm from the frontend that the UI submits the window in seconds. A grep of the static sources found nothing relevant.

**Fix:** decide the unit once and make the code and UI agree. If the stored value is seconds (as the model says), existing filters with a window of 120 need to be updated to 7200 to keep the 2-hour behavior. If the UI means minutes, convert in `filter_dedup` again. I have not changed any code.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The custom deduplicate-filter branch now passes `f.window` (a window the UI sets in minutes, 120 = 2 hours) straight to `_window_start`, which treats it as seconds, so the lookback shrinks to 2 minutes.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef