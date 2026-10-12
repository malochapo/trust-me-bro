`_should_update_signal_message` decides this. I read it in `src/dispatch/signal/flows.py`, and the only place it's called is the dedup branch near line 94. I didn't run anything.

- **First repeat for a case:** if the case has no entry in the cache, the function returns True and records the time.
- **Later repeats:** the function returns True only if all of these hold:
  - the signal's filter action is `deduplicate`;
  - the case already has a `signal_thread_ts`;
  - at least 5 seconds have passed since the last redraw recorded for that case. The comparison is between the two signal instances' `created_at` timestamps, and the cache is updated each time the function returns True.
- **Cache lifetime:** the per-case record sits in a `TTLCache` with a 60-second TTL and `maxsize=4`. If a case's entry expires or is evicted, the next repeat counts as a first one and redraws immediately.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds