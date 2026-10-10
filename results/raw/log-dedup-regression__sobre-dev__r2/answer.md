The root cause is a units bug in `filter_dedup` in `src/dispatch/signal/service.py`. Commit `9dc24f46` changed how the deduplication filter's window is read, and it now treats minutes as seconds.

- **Before the commit:** the filter used `timedelta(minutes=f.window)`, so a window of 120 meant 120 minutes.
- **After the commit:** the code calls the new helper `_window_start(f.window)`, which does `timedelta(seconds=seconds)`. The comment added with it says "SignalFilter.window is stored in seconds". That is wrong: the value is still entered in minutes. The refactor only converted the no-filter default branch (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`) correctly.
- **Effect on this signal:** the effective window shrank from 120 minutes to 120 seconds, so each instance only joins a case if an earlier one arrived in the last 2 minutes.
- **Why only this signal:** signals with no filter use the default branch, which was converted correctly, so they are fine.

**Log evidence:**
- On 2025-08-13 the worker logs one new case every few hours, with many `filtered: action=deduplicate` lines in between.
- From about 21:42 UTC on 2025-08-14 (a new worker pod, `tlmhd`, started then), cases are created every few minutes (48663, 48668, 48672, 48675, …).
- The commit is dated 2025-08-14 12:15 -05:00, which is 17:15 UTC. I'm inferring that the pod start is the deploy of that commit; the log doesn't state it.

I didn't confirm in the UI code that the field is labelled in minutes. I inferred it from the pre-commit behaviour and the 120 you set.

The fix is to pass `f.window * 60` to `_window_start`, or to change `_window_start` to take minutes. The "stored in seconds" comment should go either way. `models.py:206` also says the column is in seconds, with a default of `60 * 60`, which would mean 3600 minutes if the unit is minutes. That's worth a look, but I haven't changed it.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor passes the filter's window (entered and previously used as minutes) to `_window_start`, which treats it as seconds, so a 120-minute dedup window shrank to 120 seconds.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef