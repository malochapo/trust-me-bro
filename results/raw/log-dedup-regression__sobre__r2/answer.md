The signal's 120 dedup window is now read as 120 seconds instead of 120 minutes, so almost nothing falls inside it.

- **Timing:** The worker started image `main-8298f999` at 2025-08-14T20:05. Right after that, GuardDuty cases switch from one every ~4 hours to several per hour. Between 21:42 and 22:13 on 08-14 there are five new cases, 48663, 48668, 48672, 48675 and 48678. Before the deploy, repeats joined the open case.
- **Change:** Commit `9dc24f46` ("refactor(signal): share the lookback window computation", 2025-08-14) added `_window_start(seconds)`.
- **Faulty code:** In `filter_dedup`, the old line `timedelta(minutes=f.window)` became `_window_start(f.window)`, which uses `timedelta(seconds=...)`. A comment was added saying the window is stored in seconds. The UI and the pre-existing behaviour used minutes. The `SignalFilter.window` column comment says seconds, but its default of `60 * 60` is also minute-sized.
- **Why other signals look fine:** A signal with no filters takes the default-window branch. That branch was changed with `* 60`, which keeps it correct. Only signals with an explicit deduplicate filter are affected.
- **Not checked:** I searched the Vue files in `src/dispatch/static/dispatch/src/signal/` for "window" and got no hits, so I did not confirm the unit from the UI code. The minutes reading rests on the old code, the 120 you see in the UI, and the log pattern.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor changed the per-filter dedup lookback from `timedelta(minutes=f.window)` to `_window_start(f.window)`, which uses seconds, so a window of 120 now means 2 minutes instead of 2 hours and repeat signals no longer match the open case.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef