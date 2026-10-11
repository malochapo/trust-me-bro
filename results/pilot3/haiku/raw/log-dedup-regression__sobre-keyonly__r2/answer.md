**Root cause:** commit `9dc24f46` changed how `filter_dedup` reads a filter's `window`. Before it, the value was treated as minutes (`timedelta(minutes=f.window)`). After it, the value is passed to `_window_start()`, which treats it as seconds. The UI still stores the 120 that the on-call set under the old minute meaning, so the lookback shrank from 120 minutes to 120 seconds. Any two GuardDuty instances more than 2 minutes apart no longer match, so each one opens a new case. Signals with no filters use the separate default path, which still multiplies by 60 correctly, so they are unaffected.

**Evidence from the log:**
- Up to about 19:50 UTC on 2025-08-14, GuardDuty instances arrived 6–13 minutes apart and were deduplicated into the open case (for example 19:04 created case 48637, then 19:15, 19:26, 19:38, 19:44, and 19:50 were all `deduplicate`).
- The first new case after the 20:05 worker restart (image `main-8298f999`) is at 21:42. From then on, most instances create a case. The exceptions are the few that land within about a minute of an existing case: 21:56:23→21:56:42 (19 s), 00:39:24→00:39:51 (27 s), 00:44:45→00:45:39 (54 s), 03:50:18→03:51:15 (57 s). That matches a 120-second window.

**Caveat:** I did not check the deployed image's source or the UI's unit conversion. The model comment and the default (`600`, `60 * 60`) say seconds, so the stored value is arguably in the wrong unit. The fix is either to restore minute semantics in `filter_dedup` or to convert the stored values. Either way, existing filters with a window of 120 need to be checked. I did not change any code.

FILE: src/dispatch/signal/service.py
FUNCTION: filter_dedup
CAUSE: The refactor in commit 9dc24f46 changed the filter window from minutes to seconds (`_window_start(f.window)` instead of `timedelta(minutes=f.window)`), so the existing 120-minute GuardDuty window became 120 seconds and instances more than 2 minutes apart stop deduplicating.
INTRODUCED_BY: 9dc24f46