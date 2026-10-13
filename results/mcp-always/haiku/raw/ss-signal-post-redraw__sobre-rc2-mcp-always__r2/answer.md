The function is `_should_update_signal_message` in `src/dispatch/signal/flows.py` (lines 351–382). It decides whether a repeat gets its alert post redrawn.

It returns True when:
- there is no cached entry for the case yet (the first signal for that case always redraws), or
- the signal's filter action is `deduplicate`, the case has a `signal_thread_ts`, and at least 5 seconds have passed since the last redraw recorded in the cache.

The cache stores the timestamp only when a redraw happens, so the 5 seconds is measured from the last redraw, not from the previous repeat. The cache is a `TTLCache` with a 60-second TTL (line 348), so an entry expires after 60 seconds and the next signal for that case redraws again.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds