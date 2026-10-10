The root cause is commit 9dc24f46, "refactor(signal): share the lookback window computation", authored 2025-08-14 12:15 -0500. It made the per-filter dedup window 60 times shorter than before.

- **Timing:** the log shows a new worker pod (`tlmhd`) starting at 20:05Z on 08-14. The last GuardDuty dedup was at 19:50Z. From 21:42Z onward, GuardDuty signals mostly open a new case each time. Before that, they were deduplicated into one case for hours.
- **Before the refactor:** `filter_dedup` computed `window = now - timedelta(minutes=f.window)`. A window of 120 meant 120 minutes.
- **After the refactor:** the new helper `_window_start(seconds)` uses `timedelta(seconds=...)`. The filter branch now calls `_window_start(f.window)` under the comment "SignalFilter.window is stored in seconds". The stored 120 is therefore read as 120 seconds, so the lookback shrinks from 2 hours to 2 minutes.
- **Why GuardDuty and not other signals:** GuardDuty alerts arrive roughly 5–10 minutes apart, so with a 2-minute window the earlier instance is always outside it. Other signals probably either use the default path or have windows that don't matter at that scale.
- **Default path unaffected:** the no-filters path multiplies `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` by 60, so it still behaves as before.
- **Unit mismatch to resolve:** the model comment says "number of seconds", but the previous behavior was minutes. I did not check the UI label or the migration history. The log pattern and the "120 in the UI" report fit minutes. The fix is to restore minutes for `f.window`, for example `_window_start(f.window * 60)`.
- **What I didn't do:** I haven't changed any code or tested a fix.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor changed the per-filter dedup window from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which uses seconds, so a 120-minute window became 120 seconds and open cases fell outside the lookback.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef