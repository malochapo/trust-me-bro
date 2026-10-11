The root cause is commit 9dc24f46, a refactor made on 2025-08-14. It changed the unit that `filter_dedup` applies to a signal filter's `window`. I didn't run the code, and I didn't check the log for new cases after the commit.

- **Before:** `filter_dedup` used `timedelta(minutes=f.window)`, so a window of 120 meant a 2-hour lookback.
- **After:** the refactor added a helper `_window_start(seconds)` and switched the call to `_window_start(f.window)`. A comment added in the same commit claims the window "is stored in seconds".
- **Effect:** the same value of 120 is now read as 120 seconds, a 2-minute lookback.
- **Result:** the "GuardDuty: Unauthorized API call" signals don't arrive within 2 minutes of each other. Each one finds no earlier instance in its window and opens a new case.
- **Other signals:** the same-commit change to the default-window path (no filters) multiplies the minutes constant by 60, so it behaves as before. That fits other signals looking fine.
- **Log evidence:** on 2025-08-13 this signal deduplicated into case 48222 for over an hour, with gaps of several minutes between instances. That would not have worked with a 2-minute window.
- **Ambiguity:** the model comment on `SignalFilter.window` also says "seconds" (`src/dispatch/signal/models.py:206`), but the original behaviour was minutes. The UI shows 120 and the filter was never edited, so the refactor's reading of the unit is the change.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor changed the filter window from minutes to seconds (`_window_start(f.window)` replacing `timedelta(minutes=f.window)`), so a window of 120 now means 2 minutes instead of 2 hours and almost no signals deduplicate.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef