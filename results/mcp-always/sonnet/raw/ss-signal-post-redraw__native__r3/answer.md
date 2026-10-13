`_should_update_signal_message` in `src/dispatch/signal/flows.py` (line 351) decides this. A repeat gets the post redrawn only if all of these hold:

- Its filter action is `deduplicate`.
- The case already has a `signal_thread_ts`, meaning a signal post exists in the thread.
- At least 5 seconds have passed since the last redraw for that case. The code compares the new instance's `created_at` with the cached `created_at` of the last redraw, using `>= timedelta(seconds=5)`.

The first repeat for a case with no cache entry is always allowed, and it starts the 5-second clock.

The cache is a `TTLCache` with `maxsize=4` and `ttl=60`. Entries expire after 60 seconds, and only 4 cases are tracked at once. An expired or evicted entry makes the next repeat count as a first one, so it is allowed. In practice, the 5-second gap is the throttle.

FILE: src/dispatch/signal/flows.py
FUNCTION: _should_update_signal_message
MIN_GAP: 5 seconds