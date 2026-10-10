The cause is a unit change in `filter_dedup`. Since commit 9dc24f46, a signal filter's deduplication window is read as seconds, but the UI and the stored values use minutes.

The UI labels the field "Window (minutes)", so 120 means 120 minutes. The commit "refactor(signal): share the lookback window computation" went in at 12:15 -0500 on 2025-08-14. It replaced `timedelta(minutes=f.window)` with `_window_start(f.window)`, where the new helper takes seconds, and added a comment claiming `SignalFilter.window` is "stored in seconds".

As a result, the "GuardDuty: Unauthorized API call" filter's 120 now looks back 2 minutes instead of 2 hours. Signals that arrive more than 2 minutes after the first one no longer find the open case, so each one opens a new case.

The signal worker log is consistent with this:
- Before the change, each case absorbed about 8 to 11 follow-up signals through `action=deduplicate` over a couple of hours.
- On 2025-08-14 the worker that wrote the log changed, from `signal-worker-6d9c7b8f5-q5hjq` to `signal-worker-6d9c7b8f5-tlmhd`, and the signals stopped deduplicating. From 21:42 UTC it logs `created case` back to back: cases 48663, 48668, 48672, 48675 and 48678, then a long run on 08-15. I did not check the log timestamps against the commit time.
- Other signals are unaffected because they have no filter, or use the default window, which `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` converts correctly.

One thing I did not rule out: the model comment at `src/dispatch/signal/models.py:206` says the column is in seconds. That comment is misleading and may have prompted the refactor, but the UI and the pre-refactor behaviour both use minutes. The fix is to restore `timedelta(minutes=f.window)` or call `_window_start(f.window * 60)`, and to correct the comments. I have not changed any code.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor made the per-filter dedup window `_window_start(f.window)`, which reads the value (120, set in minutes in the UI) as seconds, so the lookback shrank from 2 hours to 2 minutes.
INTRODUCED_BY: 9dc24f46