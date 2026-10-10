**Root cause:** commit `9dc24f46` ("refactor(signal): share the lookback window computation", 2025-08-14 12:15 -0500, which is 17:15Z) changed the unit of the dedup filter window from minutes to seconds.

- **Before:** `filter_dedup` computed `datetime.now(timezone.utc) - timedelta(minutes=f.window)`. The filter's 120 therefore meant a 2-hour lookback.
- **After:** it calls the new helper `_window_start(f.window)`, which does `timedelta(seconds=seconds)`. The same 120 now means a 2-minute lookback.
- **Why only this signal:** GuardDuty instances arrive roughly every 5 to 10 minutes. A 2-minute window never finds the earlier instance, so each one opens a new case.
- **Log evidence:**
  - On 2025-08-13 and early 2025-08-14, GuardDuty instances were deduplicated into one case for hours. For example, 48489 collected instances from 02:55 through at least 03:44Z.
  - From about 19:00Z on 2025-08-14, which fits a deploy of that commit, it creates a new case every few minutes, e.g. 48637 → 48663 → 48668 → 48672 on 08-14, then several per hour on 08-15.
- **Which unit is right:** the model comment in `src/dispatch/signal/models.py` says `SignalFilter.window` is in seconds, and the refactor follows it. The window of 120 set in the UI was written against the old minutes behaviour, so the refactor changed behaviour for existing filters. I did not check the UI label for the field. Either the unit has to be settled and the stored values migrated, or the helper call has to be restored to minutes.
- **Other signals:** I didn't check why they look fine. They probably have no filter, or a window large enough to survive the change.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor replaced `timedelta(minutes=f.window)` with `_window_start(f.window)`, which treats the value as seconds, so the filter's window of 120 shrank from 2 hours to 2 minutes and repeat signals no longer match the open case.
INTRODUCED_BY: 9dc24f4634eb895b3d98b168e931306c3131dfef