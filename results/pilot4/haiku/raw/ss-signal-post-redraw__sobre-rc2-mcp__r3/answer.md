The function is `_should_update_signal_message` in `src/dispatch/signal/flows.py`, at line 351. It decides whether a repeat gets the alert post redrawn, and the redraw itself is done by `update_signal_message` (line 329), which the caller only invokes when this check returns true.

The check returns true in two cases:

- **No cache entry for the case yet:** the first repeat always triggers a redraw and records the time.
- **The repeat is a deduplicate action, the case has a `signal_thread_ts`, and at least 5 seconds have passed since the last recorded redraw:** it redraws and updates the recorded time.

Otherwise it returns false and the post is left alone. The 5-second gap is measured between the repeat's `created_at` and the cached `created_at` of the last redraw, so it is not wall-clock time.

The "last redraw" timestamp lives in an in-process `TTLCache` (`_last_nonupdated_signal_cache`, `maxsize=4`, `ttl=60`). Entries older than 60 seconds expire, and with only four slots, the cache can hold entries for at most four cases. Because the cache is per process, a second worker would keep its own timestamps. I did not run anything or change any code.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds