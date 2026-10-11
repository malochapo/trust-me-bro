The cause is in `filter_dedup`, in a refactor commit from the afternoon of 2025-08-14. The refactor treats the filter's window as seconds, but the code and the UI have always treated it as minutes.

- **Log evidence:** On 08-13 and early 08-14, GuardDuty instances arriving 6–12 minutes apart are deduplicated into the same case (for example case 48222 and case 48254). That is only possible if the stored value, 120, means 120 minutes.
- **The change:** Commit 9dc24f46 (Aug 14, 2025) replaced `timedelta(minutes=f.window)` with a new helper, `_window_start(f.window)`. The helper does `timedelta(seconds=...)`, and a comment added in the same change says "SignalFilter.window is stored in seconds".
- **Effect:** A filter window of 120 now means 2 minutes instead of 2 hours. Almost every new instance falls outside that window and opens a new case.
- **Other signals:** Signals with no filters go through the default-window branch. That branch multiplies its minutes constant by 60 before calling the helper, so it still gives the right window. This matches the report that other signals look fine.
- **Model comment:** The `SignalFilter.window` column comment in `models.py` says seconds, which conflicts with the pre-refactor behaviour and with the UI value. I didn't check how the UI labels the field. The refactor author appears to have followed that comment.

I haven't changed any code. The fix would be to pass `f.window * 60` to the helper at the filter call site. The model comment should also be corrected.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor passes the per-filter `f.window` (stored in minutes, e.g. 120) to the new `_window_start` helper, which treats it as seconds, so a 120-minute dedup window shrinks to 2 minutes and new signals no longer match the open case.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef