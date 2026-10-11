The root cause is a units mismatch introduced by commit `9dc24f46`, which switched the dedup lookback from minutes to seconds without converting the stored value.

**What changed:** Before the commit, `filter_dedup` computed the window as `timedelta(minutes=f.window)`. The refactor replaced that with `_window_start(f.window)`, and `_window_start` treats its argument as seconds. The new comment, "SignalFilter.window is stored in seconds", reflects the model's intent, but the data was never converted.

**Why this matters:** The UI (`SignalFilterCreateDialog.vue`) labels the field "Window (minutes)" and submits the raw value without multiplying by 60. So the stored `120` means 120 minutes. After the commit it is read as 120 seconds, a 2-minute lookback. Any GuardDuty instance more than about 2 minutes after the last one finds no match and opens a new case. Other signals are unaffected because they use the default path, which the same commit converts correctly (`SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60`).

**Log evidence:** Through 2025-08-14 the GuardDuty instances deduplicate across gaps of up to about 12 minutes. From 21:42 on 2025-08-14, on pod `signal-worker-…-tlmhd`, nearly every instance creates a new case: 21:42, 21:52, 21:56, 22:02, 22:13, each 4 to 11 minutes apart. Those gaps match a 2-minute window. The timeline is not perfectly clean, though. A few dedups around 14:40 and 19:38 on 08-14 came after gaps of about 12 minutes, so I did not pin the exact deploy time. The commit's timestamp is 17:15 UTC, and the pod change at 21:42 is the likeliest rollout point.

**Fix options (not applied):** Either restore `timedelta(minutes=f.window)` in `filter_dedup`, or make the UI/API convert minutes to seconds and migrate existing rows. The first is the smaller change. Since the stored values are currently minutes, rows already in the database are correct for the restored code.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: Commit 9dc24f46 began treating SignalFilter.window (entered in minutes by the UI and stored unconverted) as seconds, shrinking every custom dedup window of 120 to 2 minutes.
INTRODUCED_BY: 9dc24f46