The cause is commit 9dc24f46 (2025-08-14), which changed the dedup lookback for signals that have a filter from minutes to seconds, so the 120 window shrank from 2 hours to 2 minutes.

- **Log pattern:** On 2025-08-13 and early 2025-08-14, GuardDuty instances arrive every few minutes after a `created case` line and are logged as `filtered: action=deduplicate`. That is consistent with a 120-minute window. By the evening of 2025-08-14 (21:42 onward), they almost all log `created case` instead.
- **Before the commit:** `filter_dedup` in `src/dispatch/signal/service.py` computed the window as `datetime.now(timezone.utc) - timedelta(minutes=f.window)`. `f.window` is the value from the filter, so 120 meant 120 minutes.
- **The commit:** It added a helper, `_window_start(seconds)`, which builds the window with `timedelta(seconds=seconds)`. The filter path was switched to `_window_start(f.window)`, with a comment saying the value is stored in seconds.
- **Other signals unaffected:** The default path for signals with no filter was changed to `_window_start(SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60)`, which keeps the same duration. That would explain why other signals still look fine.
- **Which unit is right:** The `SignalFilter.window` column comment in `src/dispatch/signal/models.py` says seconds, which is probably where the refactor got its assumption. But the log shows dedup working across gaps of an hour or more before the commit, so the UI value of 120 was being treated as minutes. The commit changed the unit the existing filter values are read in.
- **Unconfirmed:** I did not check how the UI labels the field, so the minutes-versus-seconds question is settled only by that log behaviour.
- **Timing:** The commit is stamped 2025-08-14 12:15 -0500. I did not confirm when it reached the workers, only that the behaviour changes during 2025-08-14.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor made filter_dedup compute the filter's lookback window via `_window_start(f.window)` using seconds instead of the previous `timedelta(minutes=f.window)`, so a window of 120 shrank from 2 hours to 2 minutes and repeat signals no longer match the open case.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef