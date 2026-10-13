The function is `_should_update_signal_message` in `src/dispatch/signal/flows.py` (lines 351–382). It decides whether a repeat gets its alert post redrawn in the case thread.

The gap is 5 seconds. A repeat triggers a redraw only when all of these hold:
- the signal's filter action is `deduplicate`,
- the case has a `signal_thread_ts`,
- at least 5 seconds have passed since the last redraw for that case, measured from `created_at` of the cached entry.

The last-redraw timestamps are kept in `_last_nonupdated_signal_cache`, a `TTLCache` with `maxsize=4` and `ttl=60`. Entries expire after 60 seconds. The first signal for a case always returns True and seeds the cache.

Note that the function's own docstring and the cache comment call the cached entry "last update," but the cache is only refreshed on a redraw, so the timestamp is the last redraw, not the last repeat.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds