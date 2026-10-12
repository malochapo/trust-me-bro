The function is `_should_update_signal_message`. A repeat can trigger another redraw only if its `created_at` is at least 5 seconds after the `created_at` of the last redraw recorded for the same case. I did not open the call site at `src/dispatch/signal/flows.py:94` beyond seeing that it uses this function, so I'm taking it that the update it gates is the redraw.

A repeat is redrawn when any of these holds:
- **First repeat for the case:** the case has no entry in the cache, so it is redrawn at once.
- **Later repeats:** all of the following must hold:
  - The signal's filter action is `deduplicate`.
  - The case already has a `signal_thread_ts`, meaning the original post exists in the thread.
  - At least 5 seconds have passed since the cached timestamp.

The cache is a `TTLCache` with a 60-second TTL and `maxsize=4`. If a case's entry expires after 60 seconds, or is evicted because the cache is full, the next repeat finds no entry and is redrawn immediately. So the 5-second gap only applies while the entry is still in the cache.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds