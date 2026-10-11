The root cause is commit `9dc24f46`, "refactor(signal): share the lookback window computation". It changed how the dedup window is read, so a window of 120 now means 120 seconds instead of 120 minutes. I haven't run the code or reproduced the bug. This conclusion comes from the log pattern and the diff.

**Log evidence**
- Before 2025-08-14, GuardDuty signals joined one case for up to about 1–2 hours. For example, case 48222 absorbed 8 instances from 00:40 to 01:49.
- From the evening of 2025-08-14 onward, almost every GuardDuty signal logs `created case`. Dedup hits are rare, which is what a 2-minute window would produce for signals arriving every few minutes.
- The image running in the worker changed to `main-8298f999` at 20:05 on 2025-08-14. That build contains `9dc24f46` (authored that day, 12:15 -0500), and the log shows the new case-per-signal pattern from about 21:00.
- Other signals were unaffected. The Datadog and Okta dedup lines in the log are consistent with that.

**The faulty code**
- Before the commit, `filter_dedup` computed the window as `timedelta(minutes=f.window)`.
- The commit replaced that with `_window_start(f.window)`. That helper treats its argument as seconds, via `timedelta(seconds=seconds)`.
- A comment added in the same commit claims "SignalFilter.window is stored in seconds". The model's column comment in `src/dispatch/signal/models.py` says the same. The behaviour before the commit, and the UI value of 120, indicate minutes. The refactor "fixed" the unit to match the comment, which changed behaviour.
- The default path (no filters) multiplies `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES` by 60 before calling the helper, so it is unchanged. That is why only signals with a custom dedup filter are affected.

**Fix:** pass `f.window * 60` to `_window_start`, or restore `timedelta(minutes=f.window)`. Then fix the misleading "seconds" comments. I haven't made any change.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor made filter_dedup pass the filter's window (120, which the previous code and the UI treat as minutes) to a helper that reads it as seconds, so the dedup lookback shrank from 2 hours to 2 minutes.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef