The root cause is a unit mismatch introduced by commit `9dc24f46` on 2025-08-14. The deduplication lookback now treats the filter's `window` as seconds, but the UI and the previous code treat it as minutes.

**What changed.** Before `9dc24f46`, the lookback was `timedelta(minutes=f.window)`. The commit replaced it with `_window_start(f.window)`, and `_window_start` subtracts the value as seconds. The commit's comment says "SignalFilter.window is stored in seconds", but the UI labels the field "Window (minutes)" (`SignalFilterCreateDialog.vue:57`) and submits the raw value without conversion. So the stored 120 means 120 minutes, and the code now reads it as 120 seconds. Only signals with a custom deduplicate filter go through this path, which is why the default-window signals look fine.

**Evidence in the log.**
- Through 2025-08-14 ~17:15Z (the commit's timestamp, 12:15 -0500), GuardDuty signals joined existing cases, for example `filtered: action=deduplicate case_id=48593` at 15:08Z.
- Starting at 21:42Z, every GuardDuty signal `created case` a new case (48663, 48668, 48672, 48675, 48678), with only occasional joins to a case created within the last couple of minutes (e.g. 48672 at 21:56:42Z, 16 seconds after it was created).

I did not change any code. The fix is to convert the minutes value to seconds at the call site, `_window_start(f.window * 60)`, or to decide the unit explicitly and fix the stored/comment side. The model's comment and schema default (`window = 60 * 60` "seconds", `window: int | None = 600`) also disagree with the UI's minutes label, so the team should settle the unit when fixing this.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: Commit 9dc24f46 changed the custom-filter lookback from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the minutes-based window (set to 120 in the UI) as seconds, shrinking the lookback to 2 minutes so the signal misses the open case.
INTRODUCED_BY: 9dc24f46