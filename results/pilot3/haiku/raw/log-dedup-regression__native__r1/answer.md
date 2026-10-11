**Root cause:** commit `9dc24f46` changed how `filter_dedup` interprets a filter's `window`. Before it, the value was treated as minutes. Now it is passed to `_window_start` as seconds, so the stored `120` became a 2-minute lookback instead of 2 hours.

**Evidence:**
- **Before the commit**, the code was `timedelta(minutes=f.window)`. The UI's window choices are 5–30 (minutes), and the code had used minutes since `ecbad47f` (2022). The model's column comment says "seconds", but that comment was never what the dedup code actually did.
- **The diff**: `window = datetime.now(...) - timedelta(minutes=f.window)` became `window = _window_start(f.window)`, with the comment "SignalFilter.window is stored in seconds". No `* 60` was added, and existing rows were not migrated.
- **The default path is unaffected**: signals with no custom filter use `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`, which is correct. That is why the other signals look fine.
- **The logs match a 2-minute window after the change**: from 2025-08-14 21:56:23 a new case (48672) is followed by a dedup 19 seconds later, then a new case at 22:02, about 6 minutes later. Before that, dedup held across gaps of 10 to 80 minutes, which a 120-minute window would allow and a 2-minute window would not. The new-case breakage starts around 21:42Z, after the 17:15Z commit time, which probably reflects when the new code was deployed; I could not confirm the deploy time.

**Fix (not applied):** restore the minute conversion in `filter_dedup`, i.e. `_window_start(f.window * 60)`, and fix the misleading "stored in seconds" comment. If the team really wants seconds, the existing filter rows (window=120 meaning minutes) must be migrated instead. I did not run tests or reproduce this; the conclusion rests on the diff and the logs.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The window of a custom dedup filter (stored as minutes in the UI) is now passed to `_window_start` as seconds, shrinking a 120-minute lookback to 120 seconds.
INTRODUCED_BY: 9dc24f46