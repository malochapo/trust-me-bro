The root cause is a units mismatch introduced by commit `9dc24f46` on 2025-08-14. The refactor changed the lookback window from minutes to seconds, but the stored `SignalFilter.window` values are still minutes. A window of 120 is now read as 120 seconds, so the dedup query only looks back 2 minutes. GuardDuty alerts arrive roughly every 10 minutes, so they almost never find an open case to join.

**Evidence**

- **The commit changed the unit.** Before `9dc24f46`, the code was `timedelta(minutes=f.window)`. After it, the code is `_window_start(f.window)`, which subtracts `f.window` as seconds, and it added the comment "SignalFilter.window is stored in seconds."
- **The UI uses minutes.** `SignalFilterCreateDialog.vue` labels the field "Window (minutes)" with options 5–30. The on-call report says the window is 120, which means minutes.
- **The log shows the break.** GuardDuty dedup worked up to about 15:08Z on 08-14. The commit landed at 17:15Z (12:15 -0500). The first GuardDuty case created after a long run of dedups is at 19:04Z (case 48637). From then on the log shows a new case or a dedup roughly every 10 minutes, which fits a 2-minute window.
- **Other signals are unaffected.** Signals with no filters take the default-window branch, which still multiplies `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` correctly. Only signals with a custom deduplicate filter use the broken path.

**Fix (not applied)**

Change `_window_start(f.window)` back to `_window_start(f.window * 60)` in `filter_dedup`, and correct the comment. The `SignalFilter.window` column comment in `models.py` says "number of seconds" and is also wrong, but the UI and the on-call data both say minutes, so the column should be treated as minutes. Existing filters with stored values such as 120 would then start working again without a data migration.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The window was changed to be read as seconds (`_window_start(f.window)`), but the stored SignalFilter.window value is in minutes, so the 120-minute window became a 2-minute lookback.
INTRODUCED_BY: 9dc24f46