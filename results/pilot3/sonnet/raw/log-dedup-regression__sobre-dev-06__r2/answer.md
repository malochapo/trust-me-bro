The root cause is a unit change in a refactor. `filter_dedup` now treats the filter's window as seconds, but the UI and the stored data use minutes. Your 120 is 120 minutes, and it is now being read as 120 seconds.

- **Evidence in the repo:** the filter dialog labels the field "Window (minutes)" (`SignalFilterCreateDialog.vue:56`). Before commit `9dc24f46` (2025-08-14), the code did `timedelta(minutes=f.window)`.
- **What the refactor did:** `9dc24f46` replaced that line with `_window_start(f.window)`, which does `timedelta(seconds=seconds)`. It also added the comment "SignalFilter.window is stored in seconds", which is wrong for the data in the UI. The default-window branch was converted correctly with `* 60`, which is why it still works.
- **Effect:** an instance only joins an open case if a matching one arrived within the last 2 minutes. Signals that arrive further apart than that each open a new case.
- **Why only this signal:** other signals probably have no custom filter, so they use the default window, which was converted correctly. I did not check that against the data.
- **Timing:** the commit is dated 2025-08-14 12:15 -0500. The log shows dedup still working early on 08-14, with 8 dedups after the 02:55 case. By 2025-08-15 most instances of this signal create a new case. I did not pin down the exact instance where it first failed.
- **Caveat on the data:** I assumed the stored `window` values are in minutes, based on the UI label and the old code. I did not query the database. The model comment says "seconds" and defaults to `60 * 60`, which conflicts with the UI. The fix should convert at the call site (`f.window * 60`) rather than change the stored data, since existing filters hold minute values.

I did not change any code.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor changed the filter lookback from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which treats the minute-valued window as seconds, so a window of 120 minutes becomes 120 seconds and dedup stops matching open cases.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef