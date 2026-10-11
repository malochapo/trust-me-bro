The root cause is the refactor in commit 9dc24f46, which changed how `filter_dedup` reads the filter's window from minutes to seconds.

- **Before:** `filter_dedup` used `timedelta(minutes=f.window)`. A window of 120 meant 120 minutes, which is what the UI sets.
- **After:** `_window_start(f.window)` is called with `f.window` unchanged, and the helper does `timedelta(seconds=seconds)`. The new comment "SignalFilter.window is stored in seconds" is wrong, because the value is in minutes. A window of 120 now means 2 minutes.
- **Effect on GuardDuty:** this signal fires every few minutes. Instances more than 2 minutes after the first one no longer find a match, so each one opens a new case.
- **Other signals:** the default-window branch of the same refactor passes `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` and still gets the right window. Signals without a custom filter are therefore unaffected. Other signals with a filter may also have a wrong window but a long one, so they may not show it.

Log evidence: I only checked the change against the log timing. On 2025-08-13 and early 2025-08-14 the log shows one case per several hours with many deduplicated instances. The commit is dated 2025-08-14 12:15 -0500, which is 17:15 UTC. The log lines where a case is created for this signal bunch up at lines 4296–4935, after roughly line 4000. I did not read the timestamps on those lines, so I haven't confirmed that the change in pattern starts at 17:15 UTC. I also did not run any code.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor passes the filter's window, stored in minutes, to `_window_start`, which reads it as seconds, so a 120-minute dedup window shrinks to 2 minutes and later instances open new cases.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef