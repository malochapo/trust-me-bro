The cause is a unit change in the dedup window lookup: the stored `window` value is in minutes, but a refactor on 2025-08-14 made the code treat it as seconds. The log shows no GuardDuty dedup after that point, which fits the timing.

- **The UI stores minutes.** The filter dialog labels the field "Window (minutes)" (`SignalFilterCreateDialog.vue:56`), so 120 means 120 minutes. The comment on the model column (`models.py:206`) says seconds, but the UI and the old code both used minutes.
- **The old code used minutes.** `filter_dedup` computed `timedelta(minutes=f.window)`.
- **The new code uses seconds.** Commit `9dc24f46` ("refactor(signal): share the lookback window computation", 2025-08-14 12:15) added a `_window_start(seconds)` helper. The signal-filter branch now calls `_window_start(f.window)`, so the lookback shrinks from 120 minutes to 120 seconds. Unless another instance of that signal fired within the last two minutes, nothing matches and a new case opens.
- **Other signals are likely unaffected.** I haven't checked their filters. If they have no filters, they take the default-window branch, where the same commit multiplies minutes by 60, so that branch is correct. I'd guess they either use that branch or have large enough windows to mask the problem, but I haven't confirmed which.

I didn't confirm from the log that the first GuardDuty case-per-instance happens after 12:15 on 08-14, and I haven't edited any code. The fix is to pass `f.window * 60` in the filter branch and correct the misleading comment, or to change the helper to take minutes.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor passes the signal filter's `window` (stored and shown in the UI as minutes) to `_window_start()`, which treats it as seconds, so a 120-minute dedup window shrinks to 120 seconds.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef