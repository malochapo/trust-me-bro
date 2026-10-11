The root cause is a unit change in `filter_dedup` from commit `9dc24f46`. The filter window of 120 is now read as 120 seconds, not 120 minutes.

**What changed:** Before `9dc24f46`, the custom-filter path computed the lookback as `datetime.now(timezone.utc) - timedelta(minutes=f.window)`. The refactor replaced it with `_window_start(f.window)`, and `_window_start` treats its argument as seconds. The new comment, `# SignalFilter.window is stored in seconds`, reflects that reading, but the UI value of 120 was entered under the minutes interpretation.

**Log evidence:** The GuardDuty outcomes split cleanly at a 120-second gap between consecutive instances:
- `2025-08-15T00:39:24` created case 48698, then `00:39:51` deduplicated (27 s later).
- `2025-08-15T00:44:45` created case 48700, then `00:45:39` deduplicated (54 s later).
- `2025-08-15T20:10:25` created case 48991, then `20:11:32` deduplicated (67 s later).
- `2025-08-15T20:16:42` created case 48993, then `20:23:36` created another case (414 s later, outside the window).

Every instance that arrived within about two minutes of the previous one joined the case, and every instance arriving later opened a new one. The onset is between `2025-08-14T19:50` and `21:42` UTC, which fits `9dc24f46` (dated 17:15 UTC) being deployed a few hours later. The default-window path (no custom filter) uses `SIGNAL_DEFAULT_DEDUP_WINDOW_MINUTES * 60` and is correct, which is why other signals look fine.

**Caveat:** `SignalFilter.window` in `models.py` (default `60 * 60`, comment "number of seconds") is ambiguous. If the stored value really is seconds, the 120 in the UI would be the bug rather than the code, but the pre-refactor minutes conversion and the observed 120-second behavior point to the code. I did not check the UI's form label, and I did not change anything in the repo.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The custom-filter dedup window was changed from `timedelta(minutes=f.window)` to `_window_start(f.window)`, so a window of 120 is now read as 120 seconds instead of 120 minutes.
INTRODUCED_BY: 9dc24f46